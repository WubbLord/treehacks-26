#!/usr/bin/env python3
"""
Run the full BASALT processing pipeline end-to-end.

Pipeline:
1) Build calibration dataset from raw calibration capture
2) Mirror cam0 -> cam1 for BASALT EuRoC loader
3) Run camera calibration
4) Run camera-IMU calibration
5) Build trajectory dataset from raw trajectory capture
6) Mirror cam0 -> cam1 for BASALT EuRoC loader
7) Run BASALT VIO and save trajectory.csv
8) Post-process trajectory to relative timestamp/position/Euler CSV
"""

import argparse
import csv
import shutil
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd):
    print("\n>>", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


def pick_latest_video_file(input_dir, explicit_video=None):
    """Pick an input video file, preferring explicit path if provided."""
    if explicit_video is not None:
        p = Path(explicit_video)
        if not p.exists():
            raise FileNotFoundError(f"Explicit trajectory video not found: {p}")
        return p

    exts = [".mov", ".mp4", ".m4v", ".avi"]
    candidates = []
    for p in Path(input_dir).iterdir():
        if not p.is_file():
            continue
        if p.suffix.lower() in exts:
            # Avoid recursively picking previously generated downsample outputs.
            if "_downsampled" in p.stem:
                continue
            candidates.append(p)

    if not candidates:
        raise FileNotFoundError(f"No video file found in {input_dir}")

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def build_downsampled_video(input_video, output_video, factor, root):
    if factor <= 1:
        return input_video

    downsample_script = Path(root) / "downsample_video.py"
    if not downsample_script.exists():
        raise FileNotFoundError(f"Missing downsample script: {downsample_script}")

    run_cmd(
        [
            sys.executable,
            downsample_script,
            "--input",
            input_video,
            "--output",
            output_video,
            "--factor",
            str(factor),
        ]
    )
    return output_video


def ensure_cam1_mirror(dataset_path):
    mav0 = Path(dataset_path) / "mav0"
    cam0 = mav0 / "cam0"
    cam1 = mav0 / "cam1"
    cam0_csv = cam0 / "data.csv"
    cam0_data = cam0 / "data"

    if not cam0_csv.exists():
        raise FileNotFoundError(f"Missing cam0 csv: {cam0_csv}")
    if not cam0_data.exists():
        raise FileNotFoundError(f"Missing cam0 data dir: {cam0_data}")

    cam1.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cam0_csv, cam1 / "data.csv")

    cam1_data = cam1 / "data"
    if cam1_data.exists() or cam1_data.is_symlink():
        if cam1_data.is_symlink() or cam1_data.is_file():
            cam1_data.unlink()
        else:
            shutil.rmtree(cam1_data)
    cam1_data.symlink_to(Path("..") / "cam0" / "data")

    print(f"Mirrored cam0 -> cam1 in: {mav0}")


def validate_dataset_has_frames(dataset_path):
    """Fail fast if camera data is empty to avoid downstream BASALT crashes."""
    cam0 = Path(dataset_path) / "mav0" / "cam0"
    data_csv = cam0 / "data.csv"
    data_dir = cam0 / "data"

    if not data_csv.exists():
        raise FileNotFoundError(f"Missing camera CSV: {data_csv}")
    if not data_dir.exists():
        raise FileNotFoundError(f"Missing camera image directory: {data_dir}")

    with open(data_csv, "r", newline="") as f:
        rows = list(csv.reader(f))
    frame_rows = max(0, len(rows) - 1)
    png_count = len(list(data_dir.glob("*.png")))

    if frame_rows == 0 or png_count == 0:
        raise RuntimeError(
            "No camera frames were generated. "
            f"csv_rows={frame_rows}, png_count={png_count}. "
            "This usually means the video file was not detected or OpenCV (cv2) is missing."
        )


def clear_calibration_cache(calib_out_dir):
    """
    Remove stale BASALT calibration cache files so calibration matches current input data.
    BASALT will otherwise reuse old detected corners/poses from a previous run.
    """
    cache_files = [
        "calib-cam_detected_corners.cereal",
        "calib-cam_init_poses.cereal",
        "calib-cam-imu_detected_corners.cereal",
        "calib-cam-imu_init_poses.cereal",
    ]
    out_dir = Path(calib_out_dir)
    if not out_dir.exists():
        return
    for name in cache_files:
        p = out_dir / name
        if p.exists():
            p.unlink()
            print(f"Removed stale cache: {p}")


def main():
    root = Path(__file__).resolve().parent
    basalt_build = root / "basalt" / "build"

    parser = argparse.ArgumentParser(description="Run full BASALT data processing pipeline.")
    parser.add_argument("--calib-raw-dir", type=Path, default=root / "calibration_raw_data")
    parser.add_argument("--traj-raw-dir", type=Path, default=root / "trajectory_raw_data")
    parser.add_argument(
        "--traj-input-video",
        type=Path,
        default=None,
        help="Optional explicit trajectory video path. If not set, newest video in --traj-raw-dir is used.",
    )
    parser.add_argument("--calib-dataset-dir", type=Path, default=root / "calib_dataset")
    parser.add_argument("--traj-dataset-dir", type=Path, default=root / "trajectory_data")
    parser.add_argument("--calib-out-dir", type=Path, default=root / "calib_out")
    parser.add_argument("--basalt-build-dir", type=Path, default=basalt_build)
    parser.add_argument(
        "--aprilgrid-json",
        type=Path,
        default=root / "basalt" / "data" / "aprilgrid_6x6.json",
    )
    parser.add_argument(
        "--config-json",
        type=Path,
        default=root / "basalt" / "data" / "euroc_config.json",
    )
    parser.add_argument(
        "--trajectory-csv",
        type=Path,
        default=basalt_build / "trajectory.csv",
        help="Output path written by basalt_vio (via --save-trajectory euroc).",
    )
    parser.add_argument(
        "--postprocessed-csv",
        type=Path,
        default=root / "trajectory_postprocessed.csv",
    )
    parser.add_argument(
        "--show-gui",
        type=int,
        choices=[0, 1],
        default=0,
        help="Set to 1 to show BASALT VIO GUI.",
    )
    parser.add_argument(
        "--clear-calib-cache",
        type=int,
        choices=[0, 1],
        default=1,
        help="Delete stale BASALT .cereal cache files in calib_out before calibration (default: 1).",
    )
    parser.add_argument(
        "--traj-video-downsample-factor",
        type=int,
        default=1,
        help="Keep every Nth frame of trajectory video before conversion (e.g. 6). Default: 1 (no downsample).",
    )
    parser.add_argument(
        "--traj-downsampled-video-path",
        type=Path,
        default=None,
        help="Optional output path for downsampled trajectory video. Default: <traj-raw-dir>/<input>_downsampled_<N>x.mp4",
    )
    parser.add_argument(
        "--export-replay-assets",
        type=int,
        choices=[0, 1],
        default=1,
        help="Export replay assets to frontend/public/replay for Replay tab auto-load (default: 1).",
    )
    parser.add_argument(
        "--replay-public-dir",
        type=Path,
        default=root.parent / "frontend" / "public" / "replay",
        help="Replay static asset output directory used by frontend route /replay.",
    )
    args = parser.parse_args()

    raw_process = root / "raw_process.py"
    post_process = root / "post_process_trajectory.py"
    export_replay = root / "export_replay_assets.py"
    basalt_calibrate = args.basalt_build_dir / "basalt_calibrate"
    basalt_calibrate_imu = args.basalt_build_dir / "basalt_calibrate_imu"
    basalt_vio = args.basalt_build_dir / "basalt_vio"

    required_paths = [
        raw_process,
        post_process,
        basalt_calibrate,
        basalt_calibrate_imu,
        basalt_vio,
        args.aprilgrid_json,
        args.config_json,
    ]
    for p in required_paths:
        if not p.exists():
            raise FileNotFoundError(f"Required path not found: {p}")
    if args.export_replay_assets == 1 and not export_replay.exists():
        raise FileNotFoundError(f"Required path not found: {export_replay}")
    if args.traj_video_downsample_factor < 1:
        raise ValueError("--traj-video-downsample-factor must be >= 1")

    # 1) Build calibration dataset
    run_cmd(
        [
            sys.executable,
            raw_process,
            "--input-dir",
            args.calib_raw_dir,
            "--output-dir",
            args.calib_dataset_dir,
        ]
    )
    validate_dataset_has_frames(args.calib_dataset_dir)

    # 2) Mirror cam0 -> cam1
    ensure_cam1_mirror(args.calib_dataset_dir)

    if args.clear_calib_cache == 1:
        clear_calibration_cache(args.calib_out_dir)

    # 3) Camera calibration
    run_cmd(
        [
            basalt_calibrate,
            "--dataset-path",
            args.calib_dataset_dir,
            "--result-path",
            args.calib_out_dir,
            "--dataset-type",
            "euroc",
            "--aprilgrid",
            args.aprilgrid_json,
            "--cam-types",
            "pinhole",
            "pinhole",
        ]
    )

    # 4) Camera-IMU calibration
    run_cmd(
        [
            basalt_calibrate_imu,
            "--dataset-path",
            args.calib_dataset_dir,
            "--result-path",
            args.calib_out_dir,
            "--dataset-type",
            "euroc",
            "--aprilgrid",
            args.aprilgrid_json,
        ]
    )

    # 5) Build trajectory dataset
    traj_video = pick_latest_video_file(args.traj_raw_dir, args.traj_input_video)
    if args.traj_video_downsample_factor > 1:
        if args.traj_downsampled_video_path is not None:
            ds_video = args.traj_downsampled_video_path
        else:
            ds_video = (
                Path(args.traj_raw_dir)
                / f"{traj_video.stem}_downsampled_{args.traj_video_downsample_factor}x.mp4"
            )
        traj_video = build_downsampled_video(
            input_video=traj_video,
            output_video=ds_video,
            factor=args.traj_video_downsample_factor,
            root=root,
        )

    run_cmd(
        [
            sys.executable,
            raw_process,
            "--input-dir",
            args.traj_raw_dir,
            "--input-video",
            traj_video,
            "--output-dir",
            args.traj_dataset_dir,
        ]
    )
    validate_dataset_has_frames(args.traj_dataset_dir)

    # 6) Mirror cam0 -> cam1
    ensure_cam1_mirror(args.traj_dataset_dir)

    # 7) Run VIO
    run_cmd(
        [
            basalt_vio,
            "--dataset-path",
            args.traj_dataset_dir,
            "--cam-calib",
            args.calib_out_dir / "calibration.json",
            "--dataset-type",
            "euroc",
            "--config-path",
            args.config_json,
            "--save-trajectory",
            "euroc",
            "--show-gui",
            str(args.show_gui),
        ]
    )

    # 8) Post-process trajectory
    run_cmd(
        [
            sys.executable,
            post_process,
            "--input-csv",
            args.trajectory_csv,
            "--output-csv",
            args.postprocessed_csv,
        ]
    )

    if args.export_replay_assets == 1:
        run_cmd(
            [
                sys.executable,
                export_replay,
                "--trajectory-csv",
                args.postprocessed_csv,
                "--images-dir",
                args.traj_dataset_dir / "mav0" / "cam0" / "data",
                "--replay-public-dir",
                args.replay_public_dir,
            ]
        )

    print("\nPipeline complete.")
    print(f"Calibration:    {args.calib_out_dir / 'calibration.json'}")
    print(f"Trajectory raw: {args.trajectory_csv}")
    print(f"Trajectory out: {args.postprocessed_csv}")
    if args.export_replay_assets == 1:
        print(f"Replay assets:  {args.replay_public_dir}")


if __name__ == "__main__":
    main()

