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
import shutil
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd):
    print("\n>>", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True)


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


def main():
    root = Path(__file__).resolve().parent
    basalt_build = root / "basalt" / "build"

    parser = argparse.ArgumentParser(description="Run full BASALT data processing pipeline.")
    parser.add_argument("--calib-raw-dir", type=Path, default=root / "calibration_raw_data")
    parser.add_argument("--traj-raw-dir", type=Path, default=root / "trajectory_raw_data")
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
    args = parser.parse_args()

    raw_process = root / "raw_process.py"
    post_process = root / "post_process_trajectory.py"
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

    # 2) Mirror cam0 -> cam1
    ensure_cam1_mirror(args.calib_dataset_dir)

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
    run_cmd(
        [
            sys.executable,
            raw_process,
            "--input-dir",
            args.traj_raw_dir,
            "--output-dir",
            args.traj_dataset_dir,
        ]
    )

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

    print("\nPipeline complete.")
    print(f"Calibration:    {args.calib_out_dir / 'calibration.json'}")
    print(f"Trajectory raw: {args.trajectory_csv}")
    print(f"Trajectory out: {args.postprocessed_csv}")


if __name__ == "__main__":
    main()

