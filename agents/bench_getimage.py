"""Temporary benchmark: time each step of getImage pipeline.

Runs inside the same container image as GetImage so it has access to
the video, trajectory CSV, DepthPro model, etc.

Usage:
    modal run agents/bench_getimage.py
"""

import csv
import math
import time
from pathlib import Path

import modal
import numpy as np

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
_DEPTH_PRO = _PROJECT / "ml-depth-pro"
_DATA = _PROJECT / "data"

app = modal.App("keryx-bench")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "torch", "torchvision", "timm", "numpy<2",
        "pillow_heif", "matplotlib", "opencv-python-headless",
        "pillow",
    )
    .add_local_dir(str(_DEPTH_PRO / "src" / "depth_pro"), "/root/src/depth_pro", copy=True)
    .add_local_file(str(_DEPTH_PRO / "pyproject.toml"), "/root/pyproject.toml", copy=True)
    .run_commands("cd /root && pip install -e .")
    .add_local_file(str(_DATA / "trajectory_postprocessed.csv"), "/data/trajectory.csv", copy=True)
    .add_local_file(str(_DATA / "video.MP4"), "/data/video.MP4", copy=True)
)

checkpoint_vol = modal.Volume.from_name("depth-pro-checkpoints", create_if_missing=True)
CKPT_PATH = "/checkpoints/depth_pro.pt"


@app.function(image=image, gpu="H200", volumes={"/checkpoints": checkpoint_vol}, timeout=300)
def bench():
    import cv2
    import torch

    import depth_pro
    from depth_pro.depth_pro import DEFAULT_MONODEPTH_CONFIG_DICT, DepthProConfig

    results = {}

    # ---- 1. Load model ----
    t0 = time.perf_counter()
    config = DepthProConfig(
        patch_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.patch_encoder_preset,
        image_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.image_encoder_preset,
        decoder_features=DEFAULT_MONODEPTH_CONFIG_DICT.decoder_features,
        use_fov_head=DEFAULT_MONODEPTH_CONFIG_DICT.use_fov_head,
        fov_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.fov_encoder_preset,
        checkpoint_uri=CKPT_PATH,
    )
    model, transform = depth_pro.create_model_and_transforms(config=config)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device).half().eval()
    results["1_model_load"] = time.perf_counter() - t0

    # ---- 2. Load trajectory DB ----
    t0 = time.perf_counter()
    db = []
    with open("/data/trajectory.csv") as f:
        for row in csv.DictReader(f):
            db.append({
                "timestamp_s": float(row["timestamp_s"]),
                "x": float(row["x_m"]),
                "y": float(row["y_m"]),
                "z": float(row["z_m"]),
                "pitch": float(row["pitch_deg"]),
                "yaw": float(row["yaw_deg"]),
                "roll": float(row["roll_deg"]),
            })
    results["2_load_db"] = time.perf_counter() - t0

    # ---- 3. Open video ----
    t0 = time.perf_counter()
    cap = cv2.VideoCapture("/data/video.MP4")
    results["3_open_video"] = time.perf_counter() - t0

    # ---- 4. _find_best (linear scan) ----
    x, y, z, yaw = 0.0, 0.0, 0.0, 0.0
    t0 = time.perf_counter()
    best_score, best_idx = float("inf"), 0
    for i, e in enumerate(db):
        dx, dy, dz = e["x"] - x, e["y"] - y, e["z"] - z
        pos_d = math.sqrt(dx**2 + dy**2 + dz**2)
        d = (e["yaw"] - yaw) % 360
        dyaw = abs(d - 360 if d > 180 else d)
        ang_d = math.sqrt(dyaw**2 + e["pitch"]**2 + e["roll"]**2)
        score = pos_d + 0.05 * ang_d
        if score < best_score:
            best_score, best_idx = score, i
    src = db[best_idx]
    results["4_find_best"] = time.perf_counter() - t0

    # ---- 5. Extract frame from video ----
    t0 = time.perf_counter()
    cap.set(cv2.CAP_PROP_POS_MSEC, src["timestamp_s"] * 1000)
    ret, frame_bgr = cap.read()
    results["5_extract_frame"] = time.perf_counter() - t0

    # ---- 6. BGR→RGB conversion (replaces save-to-PNG + load_rgb) ----
    t0 = time.perf_counter()
    img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    results["6_bgr_to_rgb"] = time.perf_counter() - t0

    # ---- 7. DepthPro transform (directly from numpy array) ----
    t0 = time.perf_counter()
    image_t = transform(img_rgb).half().to(device)
    results["7_transform"] = time.perf_counter() - t0

    # ---- 8. DepthPro inference ----
    t0 = time.perf_counter()
    with torch.no_grad():
        pred = model.infer(image_t, f_px=None)
    torch.cuda.synchronize()
    results["8_depth_inference"] = time.perf_counter() - t0

    depth_m = pred["depth"].detach().float().cpu().numpy()
    focal = float(pred["focallength_px"])

    # ---- 9. Compute relative pose ----
    t0 = time.perf_counter()

    def rot_x(deg):
        th = math.radians(deg); c, s = math.cos(th), math.sin(th)
        return np.array([[1,0,0],[0,c,-s],[0,s,c]], dtype=np.float32)
    def rot_y(deg):
        th = math.radians(deg); c, s = math.cos(th), math.sin(th)
        return np.array([[c,0,s],[0,1,0],[-s,0,c]], dtype=np.float32)
    def rot_z(deg):
        th = math.radians(deg); c, s = math.cos(th), math.sin(th)
        return np.array([[c,-s,0],[s,c,0],[0,0,1]], dtype=np.float32)

    R_src = rot_y(src["yaw"]) @ rot_x(src["pitch"]) @ rot_z(src["roll"])
    R_tgt = rot_y(yaw)
    R = R_tgt @ R_src.T
    dp = np.array([x - src["x"], y - src["y"], z - src["z"]], dtype=np.float32)
    t_vec = dp @ R_src.T
    results["9_relative_pose"] = time.perf_counter() - t0

    # ---- 10a. Reproject novel view (GPU-accelerated) ----
    t0 = time.perf_counter()
    H, W = depth_m.shape
    cx, cy = (W-1)/2.0, (H-1)/2.0
    K = np.array([[focal,0,cx],[0,focal,cy],[0,0,1]], dtype=np.float32)

    K_t = torch.from_numpy(K).to(device)
    Kinv_t = torch.inverse(K_t)
    R_t = torch.from_numpy(R).to(device)
    t_t = torch.from_numpy(t_vec).to(device).reshape(1, 3)

    uu, vv = torch.meshgrid(
        torch.arange(W, dtype=torch.float32, device=device),
        torch.arange(H, dtype=torch.float32, device=device),
        indexing="xy",
    )
    pix = torch.stack([uu, vv, torch.ones_like(uu)], dim=-1).reshape(-1, 3)
    zz = torch.from_numpy(depth_m.astype(np.float32)).to(device).reshape(-1)

    valid0 = torch.isfinite(zz) & (zz > 1e-6)
    idx0 = torch.where(valid0)[0]
    pix0, z0 = pix[valid0], zz[valid0]
    X = (pix0 @ Kinv_t.T) * z0[:, None]
    Xp = (X - t_t) @ R_t.T
    zp = Xp[:, 2]
    valid1 = zp > 1e-6
    Xp, zp, src_idx = Xp[valid1], zp[valid1], idx0[valid1]
    proj = Xp @ K_t.T
    up = proj[:, 0] / (proj[:, 2] + 1e-8)
    vp = proj[:, 1] / (proj[:, 2] + 1e-8)
    ui = torch.round(up).to(torch.int64)
    vi = torch.round(vp).to(torch.int64)
    valid2 = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
    ui, vi, zp, src_idx = ui[valid2], vi[valid2], zp[valid2], src_idx[valid2]
    lin = vi * W + ui
    order = torch.argsort(zp)
    lin_s = lin[order]
    src_s = src_idx[order]
    mask = torch.ones(lin_s.shape[0], dtype=torch.bool, device=device)
    mask[1:] = lin_s[1:] != lin_s[:-1]
    unique_lin = lin_s[mask].cpu().numpy()
    chosen_src = src_s[mask].cpu().numpy()

    out = np.zeros_like(frame_bgr)
    filled = np.zeros(H * W, dtype=bool)
    out.reshape(-1, 3)[unique_lin] = frame_bgr.reshape(-1, 3)[chosen_src]
    filled[unique_lin] = True
    torch.cuda.synchronize()
    results["10a_reproject_warp_GPU"] = time.perf_counter() - t0

    # ---- 10b. Inpainting ----
    t0 = time.perf_counter()
    holes = (~filled).reshape(H, W).astype(np.uint8) * 255
    out = cv2.inpaint(out, holes, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    results["10b_inpaint"] = time.perf_counter() - t0

    # ---- 11. Encode PNG output ----
    t0 = time.perf_counter()
    _, buf = cv2.imencode(".png", out)
    results["11_encode_png"] = time.perf_counter() - t0

    cap.release()

    # ---- Print results ----
    total = sum(v for k, v in results.items() if k != "1_model_load")
    print(f"\n{'='*55}")
    print(f"{'Step':<30} {'Time':>10}")
    print(f"{'='*55}")
    for k, v in results.items():
        bar = '#' * int(v / total * 40) if k != "1_model_load" else ''
        print(f"  {k:<28} {v:>8.4f}s  {bar}")
    print(f"{'='*55}")
    print(f"  {'TOTAL (excl model load)':<28} {total:>8.4f}s")
    print(f"{'='*55}")

    return results


@app.local_entrypoint()
def main():
    results = bench.remote()
    # Already printed inside the function
