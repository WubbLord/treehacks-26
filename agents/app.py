"""Keryx – visual search agent for building exploration.

Usage (from project root):
    modal serve agents/app.py   # dev mode (hot-reload)
    modal deploy agents/app.py  # production
"""

import csv
import math
from pathlib import Path

import modal
import numpy as np

# ---------------------------------------------------------------------------
# Paths (resolved relative to this file)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
_DEPTH_PRO = _PROJECT / "ml-depth-pro"
_DATA = _PROJECT / "data"

# ---------------------------------------------------------------------------
# Modal app + container image
# ---------------------------------------------------------------------------
app = modal.App("keryx")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install(
        "torch",
        "torchvision",
        "timm",
        "numpy<2",
        "pillow_heif",
        "matplotlib",
        "opencv-python-headless",
        "pillow",
        "fastapi[standard]",
    )
    # depth_pro package
    .add_local_dir(
        str(_DEPTH_PRO / "src" / "depth_pro"),
        "/root/src/depth_pro",
        copy=True,
    )
    .add_local_file(
        str(_DEPTH_PRO / "pyproject.toml"),
        "/root/pyproject.toml",
        copy=True,
    )
    .run_commands("cd /root && pip install -e .")
    # Bake trajectory data + video into the container
    .add_local_file(
        str(_DATA / "trajectory_coordinates.csv"),
        "/data/trajectory.csv",
        copy=True,
    )
    .add_local_file(
        str(_DATA / "video.MP4"),
        "/data/video.MP4",
        copy=True,
    )
)

checkpoint_vol = modal.Volume.from_name(
    "depth-pro-checkpoints", create_if_missing=True
)
CKPT_PATH = "/checkpoints/depth_pro.pt"

# ---------------------------------------------------------------------------
# Geometry helpers (same as view_transform_modal.py)
# ---------------------------------------------------------------------------


def rot_x(deg: float) -> np.ndarray:
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float32)


def rot_y(deg: float) -> np.ndarray:
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)


def rot_z(deg: float) -> np.ndarray:
    th = math.radians(deg)
    c, s = math.cos(th), math.sin(th)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float32)


def build_K(W: int, H: int, f_px: float) -> np.ndarray:
    cx, cy = (W - 1) / 2.0, (H - 1) / 2.0
    return np.array(
        [[f_px, 0, cx], [0, f_px, cy], [0, 0, 1]], dtype=np.float32
    )


def angle_diff(a: float, b: float) -> float:
    """Shortest signed angular difference (a - b), in [-180, 180]."""
    d = (a - b) % 360
    return d - 360 if d > 180 else d


def reproject_novel_view(
    I_bgr: np.ndarray,
    D: np.ndarray,
    K: np.ndarray,
    R: np.ndarray,
    t: np.ndarray,
    inpaint_radius: int = 3,
):
    """Reproject source image to a novel viewpoint (from view_transform_modal.py)."""
    import cv2

    H, W = D.shape
    Kinv = np.linalg.inv(K).astype(np.float32)

    uu, vv = np.meshgrid(
        np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32)
    )
    ones = np.ones_like(uu, dtype=np.float32)
    pix = np.stack([uu, vv, ones], axis=-1).reshape(-1, 3)
    z = D.reshape(-1).astype(np.float32)

    valid0 = np.isfinite(z) & (z > 1e-6)
    idx0 = np.where(valid0)[0]
    pix0, z0 = pix[valid0], z[valid0]

    X = (pix0 @ Kinv.T) * z0[:, None]
    Xp = (X - t.reshape(1, 3)) @ R.T
    zp = Xp[:, 2]
    valid1 = zp > 1e-6
    Xp, zp, src_idx = Xp[valid1], zp[valid1], idx0[valid1]

    proj = Xp @ K.T
    up = proj[:, 0] / (proj[:, 2] + 1e-8)
    vp = proj[:, 1] / (proj[:, 2] + 1e-8)
    ui = np.round(up).astype(np.int32)
    vi = np.round(vp).astype(np.int32)

    valid2 = (ui >= 0) & (ui < W) & (vi >= 0) & (vi < H)
    ui, vi, zp, src_idx = (
        ui[valid2],
        vi[valid2],
        zp[valid2],
        src_idx[valid2],
    )

    lin = vi * W + ui
    order = np.argsort(zp)
    lin_s, src_s = lin[order], src_idx[order]
    unique_lin, first_pos = np.unique(lin_s, return_index=True)
    chosen_src = src_s[first_pos]

    out = np.zeros_like(I_bgr)
    filled = np.zeros(H * W, dtype=bool)
    out.reshape(-1, 3)[unique_lin] = I_bgr.reshape(-1, 3)[chosen_src]
    filled[unique_lin] = True

    holes = (~filled).reshape(H, W).astype(np.uint8) * 255
    if inpaint_radius > 0:
        out = cv2.inpaint(
            out, holes, inpaintRadius=inpaint_radius, flags=cv2.INPAINT_TELEA
        )
    return out, holes


# ---------------------------------------------------------------------------
# Image database loader (runs inside the container)
# ---------------------------------------------------------------------------


def _load_database() -> list[dict]:
    """Load trajectory metadata from the trajectory CSV.

    Returns a list of dicts with keys: x, y, z, yaw, pitch, roll, timestamp_s.
    Timestamps map directly to video timestamps for frame extraction.
    """
    traj: list[dict] = []
    with open("/data/trajectory.csv") as f:
        for row in csv.DictReader(f):
            traj.append(
                {
                    "timestamp_s": float(row["timestamp_s"]),
                    "x": float(row["x_m"]),
                    "y": float(row["y_m"]),
                    "z": float(row["z_m"]),
                    "pitch": float(row["pitch_deg"]),
                    "yaw": float(row["yaw_deg"]),
                    "roll": float(row["roll_deg"]),
                }
            )
    return traj


def _extract_frame(cap, timestamp_s: float) -> np.ndarray:
    """Extract a single frame from the video at the given timestamp.

    Returns the frame as a BGR numpy array.
    """
    import cv2

    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp_s * 1000)
    ret, frame = cap.read()
    if not ret:
        raise RuntimeError(f"Failed to read frame at {timestamp_s:.3f}s from video")
    return frame


# ---------------------------------------------------------------------------
# GetImage – persistent container class
# ---------------------------------------------------------------------------


@app.cls(
    image=image,
    gpu="H200",
    volumes={"/checkpoints": checkpoint_vol},
    timeout=600,
    scaledown_window=300,
)
class GetImage:
    """Persistent container hosting the DepthPro model and image database.

    Image selection criteria
    ========================
    Given a query pose (x, y, z, yaw) with pitch=0 and roll=0, the best
    source image is chosen by a linear scan over all 797 images.  Each
    image is scored as:

        score = pos_distance + 0.05 * ang_distance

    where pos_distance is the Euclidean distance between positions and
    ang_distance combines yaw, pitch, and roll differences.  The image
    with the lowest score is selected.

    After selecting the source image, the endpoint:
      - Runs DepthPro to estimate a dense depth map for I.
      - Computes the exact relative rotation R and translation t between
        the source camera pose and the query pose.
      - Calls reproject_novel_view(I, depth, K, R, t) to warp I into the
        requested viewpoint, with inpainting to fill disoccluded holes.
    """

    @modal.enter()
    def setup(self):
        import cv2
        import torch

        import depth_pro
        from depth_pro.depth_pro import (
            DEFAULT_MONODEPTH_CONFIG_DICT,
            DepthProConfig,
        )
        # Load DepthPro (once per container lifetime)
        config = DepthProConfig(
            patch_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.patch_encoder_preset,
            image_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.image_encoder_preset,
            decoder_features=DEFAULT_MONODEPTH_CONFIG_DICT.decoder_features,
            use_fov_head=DEFAULT_MONODEPTH_CONFIG_DICT.use_fov_head,
            fov_encoder_preset=DEFAULT_MONODEPTH_CONFIG_DICT.fov_encoder_preset,
            checkpoint_uri=CKPT_PATH,
        )
        self.model, self.transform = depth_pro.create_model_and_transforms(
            config=config
        )
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = self.model.to(self.device).half().eval()

        # Open video capture (kept open for the container lifetime)
        self.cap = cv2.VideoCapture("/data/video.MP4")
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open /data/video.MP4")

        # Build image database
        self.db = _load_database()

    def _find_best(self, x: float, y: float, z: float, yaw: float) -> int:
        """Return index of the best matching source image (linear scan)."""
        best_score, best_idx = float("inf"), 0
        best_pos_distance, best_ang_distance = 0.0, 0.0
        for i, e in enumerate(self.db):
            dx = e["x"] - x
            dy = e["y"] - y
            dz = e["z"] - z
            pos_distance = math.sqrt(dx**2 + dy**2 + dz**2)
            dyaw = abs(angle_diff(e["yaw"], yaw))
            dpitch = abs(e["pitch"])
            droll = abs(e["roll"])
            ang_distance = math.sqrt(dyaw**2 + dpitch**2 + droll**2)
            score = pos_distance + 0.05 * ang_distance
            if i % 50 == 0:
                print(f"  [{i}] t={e['timestamp_s']:.3f}s  pos_dist={pos_distance:.6f}  ang_dist={ang_distance:.6f}  score={score:.6f}")
            if score < best_score:
                best_score = score
                best_idx = i
                best_pos_distance = pos_distance
                best_ang_distance = ang_distance
        print(f"  Best: [{best_idx}] pos_dist={best_pos_distance:.6f}  ang_dist={best_ang_distance:.6f}  score={best_score:.6f}")
        return best_idx

    @modal.fastapi_endpoint()
    def getImage(self, x: float, y: float, z: float, yaw: float):
        """Synthesise a view from (x, y, z) at the given yaw (degrees).

        Pitch and roll of the output are fixed at 0.
        Returns JSON with a base64-encoded PNG.
        """
        import base64
        import tempfile

        import cv2
        import torch
        from PIL import Image as PILImage

        import depth_pro

        # 1. Pick the best source image
        idx = self._find_best(x, y, z, yaw)
        src = self.db[idx]
        print(f"Selected source frame at t={src['timestamp_s']:.3f}s")

        # 2. Extract frame from video at the matching timestamp
        frame_bgr = _extract_frame(self.cap, src["timestamp_s"])
        img_np = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(img_np)

        # 3. Depth estimation
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            pil_img.save(tmp, format="PNG")
            tmp_path = tmp.name

        image_arr, _, f_px = depth_pro.load_rgb(tmp_path)
        image_t = self.transform(image_arr).half().to(self.device)

        with torch.no_grad():
            pred = self.model.infer(image_t, f_px=f_px)

        depth_m = pred["depth"].detach().float().cpu().numpy()
        focal = float(pred["focallength_px"])

        # 4. Relative pose: source → target
        #
        #    Source camera frame: X_src = R_src @ (P_world - p_src)
        #    Target camera frame: X_tgt = R_tgt @ (P_world - p_tgt)
        #
        #    The reproject function applies:
        #        X_tgt = (X_src - t) @ R^T
        #
        #    Matching terms gives:
        #        R = R_tgt @ R_src^T
        #        t = (p_tgt - p_src) @ R_src^T
        R_src = (
            rot_y(src["yaw"]) @ rot_x(src["pitch"]) @ rot_z(src["roll"])
        )
        R_tgt = rot_y(yaw)  # target pitch=0, roll=0

        R = R_tgt @ R_src.T
        dp = np.array(
            [x - src["x"], y - src["y"], z - src["z"]], dtype=np.float32
        )
        t = dp @ R_src.T

        # 5. Reproject to novel view
        I_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        H, W = depth_m.shape
        K = build_K(W, H, focal)
        out_bgr, _ = reproject_novel_view(I_bgr, depth_m, K, R, t)

        # 6. Return base64-encoded PNG
        _, buf = cv2.imencode(".png", out_bgr)
        b64 = base64.b64encode(buf.tobytes()).decode("ascii")
        return {"image_base64": b64}

    @modal.method()
    def getImageRemote(
        self, x: float, y: float, z: float, yaw: float
    ) -> dict:
        """Same as getImage but returns a dict for programmatic callers.

        Returns: {"image_png": bytes, "source_idx": int, "source_timestamp_s": float}
        """
        import tempfile

        import cv2
        import torch
        from PIL import Image as PILImage

        import depth_pro

        idx = self._find_best(x, y, z, yaw)
        src = self.db[idx]
        print(f"Selected source frame at t={src['timestamp_s']:.3f}s")

        frame_bgr = _extract_frame(self.cap, src["timestamp_s"])
        img_np = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = PILImage.fromarray(img_np)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            pil_img.save(tmp, format="PNG")
            tmp_path = tmp.name

        image_arr, _, f_px = depth_pro.load_rgb(tmp_path)
        image_t = self.transform(image_arr).half().to(self.device)

        with torch.no_grad():
            pred = self.model.infer(image_t, f_px=f_px)

        depth_m = pred["depth"].detach().float().cpu().numpy()
        focal = float(pred["focallength_px"])

        R_src = (
            rot_y(src["yaw"]) @ rot_x(src["pitch"]) @ rot_z(src["roll"])
        )
        R_tgt = rot_y(yaw)
        R = R_tgt @ R_src.T
        dp = np.array(
            [x - src["x"], y - src["y"], z - src["z"]], dtype=np.float32
        )
        t = dp @ R_src.T

        I_bgr = frame_bgr
        H, W = depth_m.shape
        K = build_K(W, H, focal)
        out_bgr, _ = reproject_novel_view(I_bgr, depth_m, K, R, t)

        _, buf = cv2.imencode(".png", out_bgr)
        return {
            "image_png": buf.tobytes(),
            "source_idx": idx,
            "source_timestamp_s": src["timestamp_s"],
        }
