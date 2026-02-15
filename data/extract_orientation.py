#!/usr/bin/env python3
"""Extract timestamp, yaw, pitch, roll from Blackbox flight data CSV.

Reads timestamp_data.csv (Blackbox format with metadata header), pulls
the heading[0..2] columns (radians), converts to degrees, and writes a
clean CSV with columns:

    timestamp_s, yaw_deg, pitch_deg, roll_deg

Timestamp is zeroed so the first row starts at 0.

Usage:
    python data/extract_orientation.py
    python data/extract_orientation.py --input data/timestamp_data.csv --output data/orientation.csv
"""

import argparse
import csv
import math
from pathlib import Path


def find_header_row(csv_path: Path) -> tuple[int, list[str]]:
    """Find the Blackbox header row (starts with 'loopIteration')."""
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if len(row) > 0 and row[0] == "loopIteration":
                return i, row
    raise ValueError(f"Could not find header row with 'loopIteration' in {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Extract orientation from Blackbox CSV.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent / "timestamp_data.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "orientation.csv",
    )
    args = parser.parse_args()

    header_idx, header = find_header_row(args.input)

    time_col = header.index("time")
    # heading[0] = pitch, heading[1] = roll, heading[2] = yaw  (radians)
    h0_col = header.index("heading[0]")
    h1_col = header.index("heading[1]")
    h2_col = header.index("heading[2]")

    min_col = max(time_col, h0_col, h1_col, h2_col)

    rows_out: list[tuple[float, float, float, float]] = []
    first_time_us: int | None = None

    with open(args.input, "r") as f:
        reader = csv.reader(f)
        # Skip to data rows
        for _ in range(header_idx + 1):
            next(reader)

        for row in reader:
            if len(row) <= min_col:
                continue
            try:
                time_us = int(row[time_col])
                pitch_rad = float(row[h0_col])
                roll_rad = float(row[h1_col])
                yaw_rad = float(row[h2_col])
            except (ValueError, IndexError):
                continue

            if first_time_us is None:
                first_time_us = time_us

            timestamp_s = (time_us - first_time_us) / 1_000_000.0
            yaw_deg = math.degrees(yaw_rad)
            pitch_deg = math.degrees(pitch_rad)
            roll_deg = math.degrees(roll_rad)

            rows_out.append((timestamp_s, yaw_deg, pitch_deg, roll_deg))

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "yaw_deg", "pitch_deg", "roll_deg"])
        for ts, yaw, pitch, roll in rows_out:
            writer.writerow([f"{ts:.6f}", f"{yaw:.6f}", f"{pitch:.6f}", f"{roll:.6f}"])

    print(f"Wrote {len(rows_out)} rows to {args.output}")
    if rows_out:
        print(f"  Time range: {rows_out[0][0]:.3f}s – {rows_out[-1][0]:.3f}s")
        print(f"  First: yaw={rows_out[0][1]:.2f}° pitch={rows_out[0][2]:.2f}° roll={rows_out[0][3]:.2f}°")
        print(f"  Last:  yaw={rows_out[-1][1]:.2f}° pitch={rows_out[-1][2]:.2f}° roll={rows_out[-1][3]:.2f}°")


if __name__ == "__main__":
    main()
