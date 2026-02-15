#!/usr/bin/env python3
"""
Convert Blackbox flight data CSV to BASALT dataset format.

This script processes Blackbox CSV + video and converts them to:
your_dataset/
├── mav0/
│   ├── cam0/
│   │   ├── data/          # Video frames as images
│   │   └── data.csv       # Image timestamps
│   └── imu0/
│       └── data.csv       # IMU measurements
"""

import argparse
import csv
import os
import sys
from pathlib import Path

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False
    print("Warning: cv2 not available. Video frame extraction will be skipped.")
    print("Install with: pip install opencv-python")


def pick_input_file(input_dir, explicit_path, patterns, file_label):
    """Resolve an input file path from explicit path or directory scan."""
    if explicit_path:
        p = Path(explicit_path)
        if not p.exists():
            raise FileNotFoundError(f"{file_label} not found: {p}")
        return p

    candidates = []
    for pat in patterns:
        candidates.extend(sorted(input_dir.glob(pat)))

    if not candidates:
        pat_str = ", ".join(patterns)
        raise FileNotFoundError(
            f"No {file_label} found in {input_dir}. Expected one of: {pat_str}"
        )

    # Prefer newest file to keep usage simple when a folder has multiple recordings.
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    chosen = candidates[0]

    if len(candidates) > 1:
        print(
            f"Found multiple {file_label} files in {input_dir}. "
            f"Using newest: {chosen.name}"
        )

    return chosen


def find_header_row(csv_path):
    """Find the row with column headers (loopIteration, time, etc.)"""
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if len(row) > 0 and row[0] == 'loopIteration':
                return i, row
    raise ValueError("Could not find header row with 'loopIteration'")


def parse_metadata(csv_path, header_row_idx):
    """Parse metadata from the CSV header to get conversion factors."""
    metadata = {}
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i >= header_row_idx:
                break
            if len(row) >= 2 and row[0]:
                key = row[0].strip()
                value = row[1].strip()
                try:
                    # Try to convert to float
                    metadata[key] = float(value)
                except ValueError:
                    metadata[key] = value
    
    return metadata


def process_imu_data(csv_path, header_row_idx, header_row, output_path):
    """Process IMU data from CSV and write to BASALT format."""
    # Find column indices
    time_idx = header_row.index('time')
    gyro_idx = [header_row.index(f'gyroADC[{i}]') for i in range(3)]
    acc_idx = [header_row.index(f'accSmooth[{i}]') for i in range(3)]
    
    # Get conversion factors from metadata
    metadata = parse_metadata(csv_path, header_row_idx)
    gyro_scale = metadata.get('gyroScale', 1.7453292519943295e-8)  # Default from header
    acc_1g = metadata.get('acc_1G', 2048)  # Default from header
    g = 9.80665  # Standard gravity in m/s²
    
    print(f"Using gyro_scale: {gyro_scale}")
    print(f"Using acc_1G: {acc_1g}")
    
    # Open output file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as out_f:
        # Write BASALT header
        out_f.write("#timestamp [ns],w_RS_S_x [rad s^-1],w_RS_S_y [rad s^-1],w_RS_S_z [rad s^-1],a_RS_S_x [m s^-2],a_RS_S_y [m s^-2],a_RS_S_z [m s^-2]\n")
        
        # Process CSV in chunks
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            # Skip to data rows
            for _ in range(header_row_idx + 1):
                next(reader)
            
            row_count = 0
            for row in reader:
                if len(row) <= max(time_idx, max(gyro_idx), max(acc_idx)):
                    continue
                
                try:
                    # Time is in microseconds, convert to nanoseconds
                    time_us = int(row[time_idx])
                    time_ns = time_us * 1000
                    
                    # Read gyro values (raw ADC) and convert to rad/s
                    gyro_raw = [int(row[gyro_idx[i]]) if row[gyro_idx[i]] else 0 for i in range(3)]
                    gyro_rad_s = [g * gyro_scale for g in gyro_raw]
                    
                    # Read accel values (raw) and convert to m/s²
                    acc_raw = [int(row[acc_idx[i]]) if row[acc_idx[i]] else 0 for i in range(3)]
                    acc_m_s2 = [(a / acc_1g) * g for a in acc_raw]
                    
                    # Write to output
                    out_f.write(f"{time_ns},{gyro_rad_s[0]},{gyro_rad_s[1]},{gyro_rad_s[2]},{acc_m_s2[0]},{acc_m_s2[1]},{acc_m_s2[2]}\n")
                    
                    row_count += 1
                    if row_count % 10000 == 0:
                        print(f"Processed {row_count} IMU rows...")
                        
                except (ValueError, IndexError) as e:
                    # Skip invalid rows
                    continue
        
        print(f"Total IMU rows processed: {row_count}")


def extract_video_frames(video_path, output_dir, imu_start_time_ns, imu_end_time_ns):
    """Extract frames from video and match with IMU timestamps."""
    if not HAS_CV2:
        print("Skipping video frame extraction (cv2 not available)")
        return []
    
    if not os.path.exists(video_path):
        print(f"Video file not found: {video_path}")
        return []
    
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Could not open video: {video_path}")
        return []
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps > 0 else 0
    
    print(f"Video: {fps} FPS, {frame_count} frames, {duration:.2f}s duration")
    print(f"IMU time range: {imu_start_time_ns/1e9:.2f}s to {imu_end_time_ns/1e9:.2f}s")
    
    # Calculate frame timestamps
    # Assume video starts at the same time as IMU data (or adjust as needed)
    video_start_time_ns = imu_start_time_ns
    
    frame_timestamps = []
    frame_idx = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Calculate timestamp for this frame
        frame_time_ns = int(video_start_time_ns + (frame_idx / fps) * 1e9)
        
        # Save frame as image
        timestamp_str = str(frame_time_ns)
        img_path = os.path.join(output_dir, f"{timestamp_str}.png")
        cv2.imwrite(img_path, frame)
        
        frame_timestamps.append((frame_time_ns, timestamp_str))
        frame_idx += 1
        
        if frame_idx % 100 == 0:
            print(f"Extracted {frame_idx} frames...")
    
    cap.release()
    print(f"Extracted {len(frame_timestamps)} frames total")
    
    return frame_timestamps


def write_camera_csv(camera_csv_path, frame_timestamps):
    """Write camera data CSV in BASALT format."""
    os.makedirs(os.path.dirname(camera_csv_path), exist_ok=True)
    
    with open(camera_csv_path, 'w') as f:
        f.write("#timestamp [ns],filename\n")
        for timestamp_ns, filename in frame_timestamps:
            f.write(f"{timestamp_ns},{filename}.png\n")


def main():
    parser = argparse.ArgumentParser(
        description="Convert Blackbox CSV + video into BASALT EuRoC-like dataset."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(__file__).parent,
        help="Directory to scan for raw CSV/video if explicit paths are not provided.",
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=None,
        help="Path to Blackbox CSV file (e.g. *.bbl.csv).",
    )
    parser.add_argument(
        "--input-video",
        type=Path,
        default=None,
        help="Path to input video file (e.g. .mov/.mp4).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "trajectory_data",
        help="Output dataset directory (default: data/trajectory_data).",
    )
    parser.add_argument(
        "--skip-video",
        action="store_true",
        help="Only generate IMU output; do not extract video frames.",
    )

    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_base = args.output_dir.resolve()

    try:
        csv_path = pick_input_file(
            input_dir=input_dir,
            explicit_path=args.input_csv,
            patterns=["*.bbl.csv", "*.csv"],
            file_label="CSV",
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    video_path = None
    if not args.skip_video:
        try:
            video_path = pick_input_file(
                input_dir=input_dir,
                explicit_path=args.input_video,
                patterns=[
                    "*.mov", "*.mp4", "*.m4v", "*.avi",
                    "*.MOV", "*.MP4", "*.M4V", "*.AVI",
                ],
                file_label="video",
            )
        except FileNotFoundError as e:
            print(f"Warning: {e}")
            print("Continuing with IMU-only export.")

    print(f"Input CSV:   {csv_path}")
    if video_path:
        print(f"Input video: {video_path}")
    else:
        print("Input video: <none>")
    print(f"Output dir:  {output_base}")
    
    print("Finding header row...")
    header_row_idx, header_row = find_header_row(csv_path)
    print(f"Header found at row {header_row_idx + 1}")
    print(f"Columns: {header_row[:10]}...")
    
    # Create output directory structure
    imu_output = output_base / "mav0" / "imu0" / "data.csv"
    camera_output_dir = output_base / "mav0" / "cam0" / "data"
    camera_csv = output_base / "mav0" / "cam0" / "data.csv"
    
    # Create camera directory structure
    os.makedirs(camera_output_dir, exist_ok=True)
    
    # Process IMU data
    print("\nProcessing IMU data...")
    process_imu_data(csv_path, header_row_idx, header_row, imu_output)
    
    # Get IMU time range for video synchronization
    # Read first and last timestamps from IMU file
    with open(imu_output, 'r') as f:
        lines = f.readlines()
        if len(lines) > 1:
            first_time = int(lines[1].split(',')[0])
            last_time = int(lines[-1].split(',')[0])
        else:
            first_time = 0
            last_time = 0
    
    # Extract video frames
    print("\nExtracting video frames...")
    frame_timestamps = []
    if video_path is not None:
        frame_timestamps = extract_video_frames(
            video_path,
            camera_output_dir,
            first_time,
            last_time,
        )
    else:
        print("Skipping video frame extraction (no input video)")
    
    # Write camera CSV (create empty one if no frames extracted)
    if frame_timestamps:
        print("\nWriting camera data CSV...")
        write_camera_csv(camera_csv, frame_timestamps)
    else:
        # Create empty camera CSV with just header
        os.makedirs(os.path.dirname(camera_csv), exist_ok=True)
        with open(camera_csv, 'w') as f:
            f.write("#timestamp [ns],filename\n")
        print(f"\nCreated empty camera CSV at {camera_csv}")
        print("  Install opencv-python and re-run to extract video frames")
    
    print(f"\nDone! Dataset created at: {output_base}")
    print(f"  IMU data: {imu_output}")
    if frame_timestamps:
        print(f"  Camera data: {camera_csv}")
        print(f"  Camera images: {camera_output_dir}")


if __name__ == "__main__":
    main()

