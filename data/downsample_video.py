#!/usr/bin/env python3
"""
Downsample a video by keeping every Nth frame.

Example:
  python3 downsample_video.py \
    --input "/path/to/input.MP4" \
    --output "/path/to/output_6x.mp4" \
    --factor 6
"""

import argparse
from pathlib import Path

import cv2


def downsample_video(input_path: Path, output_path: Path, factor: int) -> None:
    if factor < 1:
        raise ValueError("--factor must be >= 1")
    if not input_path.exists():
        raise FileNotFoundError(f"Input video not found: {input_path}")

    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open input video: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Keep every Nth frame and lower output fps so playback speed stays similar.
    out_fps = max(fps / factor, 1e-6)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), fourcc, out_fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Failed to open output video writer: {output_path}")

    frame_idx = 0
    kept = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % factor == 0:
            writer.write(frame)
            kept += 1
        frame_idx += 1

    cap.release()
    writer.release()

    print(f"Input frames:  {total if total > 0 else frame_idx}")
    print(f"Output frames: {kept}")
    print(f"Input FPS:     {fps:.6f}")
    print(f"Output FPS:    {out_fps:.6f}")
    print(f"Wrote:         {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reduce video frame count by keeping every Nth frame.")
    parser.add_argument("--input", type=Path, required=True, help="Path to input video file")
    parser.add_argument("--output", type=Path, required=True, help="Path to output video file")
    parser.add_argument("--factor", type=int, default=6, help="Keep every Nth frame (default: 6)")
    args = parser.parse_args()

    downsample_video(args.input, args.output, args.factor)


if __name__ == "__main__":
    main()

