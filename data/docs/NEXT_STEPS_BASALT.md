# Next Steps: `raw_process.py` + BASALT

## Folder naming (important)

- `your_dataset` was a placeholder name from earlier examples.
- Canonical runtime dataset folder is now: `/Users/rohin/Desktop/code/treehacks-26/data/trajectory_data`
- Canonical calibration dataset folder is: `/Users/rohin/Desktop/code/treehacks-26/data/calib_dataset`
- If you still have `/Users/rohin/Desktop/code/treehacks-26/data/your_dataset`, it is legacy and can be ignored.

## Is `raw_process.py` sufficient?

`raw_process.py` is sufficient to:
- convert your Blackbox `data.csv` + video into EuRoC-like folder structure
- produce:
  - `mav0/cam0/data/*.png`
  - `mav0/cam0/data.csv`
  - `mav0/imu0/data.csv`

`raw_process.py` is **not** sufficient to:
- create a valid BASALT `calibration.json` for your specific camera+IMU rig
- guarantee good camera/IMU time alignment

Without a matching calibration file, `basalt_vio` often runs but outputs empty trajectory (header only).

## What to do now

1. Record a calibration dataset (AprilGrid visible + camera and IMU together).
2. Run BASALT calibration tools to produce `calibration.json`.
3. Run `basalt_vio` with your generated calibration file.
4. Save trajectory (`trajectory.csv`) and use `tx,ty,tz` as local position.

## One-command full pipeline (recommended)

Use the orchestrator script:

```bash
python3 /Users/rohin/Desktop/code/treehacks-26/data/run_full_pipeline.py
```

This runs all steps in order:
1. Build `calib_dataset` from `calibration_raw_data`
2. Mirror `cam0 -> cam1` for calibration dataset
3. Run `basalt_calibrate`
4. Run `basalt_calibrate_imu`
5. Build `trajectory_data` from `trajectory_raw_data`
6. Mirror `cam0 -> cam1` for trajectory dataset
7. Run `basalt_vio` and save `trajectory.csv`
8. Run `post_process_trajectory.py` to produce `trajectory_postprocessed.csv`

Useful variants:

```bash
# Show VIO GUI while running
python3 /Users/rohin/Desktop/code/treehacks-26/data/run_full_pipeline.py --show-gui 1

# Downsample trajectory video by 6x before processing
python3 /Users/rohin/Desktop/code/treehacks-26/data/run_full_pipeline.py \
  --traj-video-downsample-factor 6

# Override raw input folders
python3 /Users/rohin/Desktop/code/treehacks-26/data/run_full_pipeline.py \
  --calib-raw-dir /Users/rohin/Desktop/code/treehacks-26/data/calibration_raw_data \
  --traj-raw-dir /Users/rohin/Desktop/code/treehacks-26/data/trajectory_raw_data

# Full custom output paths
python3 /Users/rohin/Desktop/code/treehacks-26/data/run_full_pipeline.py \
  --calib-dataset-dir /Users/rohin/Desktop/code/treehacks-26/data/calib_dataset \
  --traj-dataset-dir /Users/rohin/Desktop/code/treehacks-26/data/trajectory_data \
  --calib-out-dir /Users/rohin/Desktop/code/treehacks-26/data/calib_out \
  --trajectory-csv /Users/rohin/Desktop/code/treehacks-26/data/basalt/build/trajectory.csv \
  --postprocessed-csv /Users/rohin/Desktop/code/treehacks-26/data/trajectory_postprocessed.csv
```

By default, the pipeline also exports replay assets to:
- `/Users/rohin/Desktop/code/treehacks-26/frontend/public/replay`

This makes the frontend `Replay` tab auto-load:
- `/replay/trajectory.csv`
- `/replay/images_manifest.json`
- `/replay/images/*.png`

## Commands

### 1) Build calibration dataset from raw logs
```bash
cd /Users/rohin/Desktop/code/treehacks-26/data
python3 raw_process.py \
  --input-dir /Users/rohin/Desktop/code/treehacks-26/data/calibration_raw_data \
  --output-dir /Users/rohin/Desktop/code/treehacks-26/data/calib_dataset
```

This should create:
- `/Users/rohin/Desktop/code/treehacks-26/data/calib_dataset/mav0/cam0/data.csv`
- `/Users/rohin/Desktop/code/treehacks-26/data/calib_dataset/mav0/cam0/data/*.png`
- `/Users/rohin/Desktop/code/treehacks-26/data/calib_dataset/mav0/imu0/data.csv`

### 1.5) Mirror `cam0` into `cam1` (required by BASALT EuRoC loader)
```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/calib_dataset/mav0
mkdir -p cam1
cp cam0/data.csv cam1/data.csv
ln -s ../cam0/data cam1/data
```

### 2) Camera calibration (intrinsics)
```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/basalt/build
./basalt_calibrate \
  --dataset-path /Users/rohin/Desktop/code/treehacks-26/data/calib_dataset \
  --result-path /Users/rohin/Desktop/code/treehacks-26/data/calib_out \
  --dataset-type euroc \
  --aprilgrid /Users/rohin/Desktop/code/treehacks-26/data/basalt/data/aprilgrid_6x6.json \
  --cam-types pinhole pinhole
```

### 3) Camera-IMU calibration
```bash
./basalt_calibrate_imu \
  --dataset-path /Users/rohin/Desktop/code/treehacks-26/data/calib_dataset \
  --result-path /Users/rohin/Desktop/code/treehacks-26/data/calib_out \
  --dataset-type euroc \
  --aprilgrid /Users/rohin/Desktop/code/treehacks-26/data/basalt/data/aprilgrid_6x6.json
```

Expected output:
- `/Users/rohin/Desktop/code/treehacks-26/data/calib_out/calibration.json`

### 4) Run VIO with your calibration
Before running VIO on runtime data, do the same `cam1` mirror step:
```bash
cd /Users/rohin/Desktop/code/treehacks-26/data/trajectory_data/mav0
mkdir -p cam1
cp cam0/data.csv cam1/data.csv
ln -s ../cam0/data cam1/data
```

Then run:
```bash
./basalt_vio \
  --dataset-path /Users/rohin/Desktop/code/treehacks-26/data/trajectory_data \
  --cam-calib /Users/rohin/Desktop/code/treehacks-26/data/calib_out/calibration.json \
  --dataset-type euroc \
  --config-path /Users/rohin/Desktop/code/treehacks-26/data/basalt/data/euroc_config.json \
  --save-trajectory euroc \
  --show-gui 1
```

## Notes

- `trajectory.csv` gives local-frame poses: `timestamp, tx, ty, tz, qw, qx, qy, qz`.
- This is not GPS lat/lon by default.
- If `trajectory.csv` is empty, check `mav0/cam1` first (missing `cam1` often causes zero associations).
- If `trajectory.csv` is empty even with `cam1`, calibration is likely mismatched or tracking failed.
- Make sure the AprilGrid file matches the board you recorded. Wrong board config will fail calibration.
- Post-process trajectory with:
```bash
python3 /Users/rohin/Desktop/code/treehacks-26/data/post_process_trajectory.py \
  --input-csv /Users/rohin/Desktop/code/treehacks-26/data/basalt/build/trajectory.csv \
  --output-csv /Users/rohin/Desktop/code/treehacks-26/data/trajectory_postprocessed.csv
```