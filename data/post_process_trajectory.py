#!/usr/bin/env python3
"""
Post-process BASALT trajectory.csv into:
timestamp_s,x_m,y_m,z_m,pitch_deg,yaw_deg,roll_deg

All outputs are relative to the first row.
"""

import argparse
import csv
import math
from pathlib import Path


def normalize_quat(qw, qx, qy, qz):
    n = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
    if n == 0:
        raise ValueError("Zero-norm quaternion encountered")
    return (qw / n, qx / n, qy / n, qz / n)


def quat_conj(q):
    w, x, y, z = q
    return (w, -x, -y, -z)


def quat_mul(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    )


def quat_to_euler_zyx_deg(q):
    w, x, y, z = q

    # roll (x)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    # pitch (y)
    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    # yaw (z)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return math.degrees(yaw), math.degrees(pitch), math.degrees(roll)


def get_indices(header):
    fields = [h.strip() for h in header]
    idx = {
        "t": None,
        "x": None,
        "y": None,
        "z": None,
        "qw": None,
        "qx": None,
        "qy": None,
        "qz": None,
    }
    for i, f in enumerate(fields):
        if f.startswith("#timestamp"):
            idx["t"] = i
        elif f.startswith("p_RS_R_x"):
            idx["x"] = i
        elif f.startswith("p_RS_R_y"):
            idx["y"] = i
        elif f.startswith("p_RS_R_z"):
            idx["z"] = i
        elif f.startswith("q_RS_w"):
            idx["qw"] = i
        elif f.startswith("q_RS_x"):
            idx["qx"] = i
        elif f.startswith("q_RS_y"):
            idx["qy"] = i
        elif f.startswith("q_RS_z"):
            idx["qz"] = i

    missing = [k for k, v in idx.items() if v is None]
    if missing:
        raise ValueError(f"Missing columns in trajectory.csv header: {missing}")
    return idx


def process(input_csv, output_csv):
    count = 0
    with open(input_csv, "r", newline="") as f_in, open(output_csv, "w", newline="") as f_out:
        reader = csv.reader(f_in)
        writer = csv.writer(f_out)

        header = next(reader, None)
        if header is None:
            raise ValueError("Empty input file")
        idx = get_indices(header)

        writer.writerow(["timestamp_s", "x_m", "y_m", "z_m", "pitch_deg", "yaw_deg", "roll_deg"])

        first = next(reader, None)
        if first is None:
            return 0

        t0 = int(first[idx["t"]])
        x0 = float(first[idx["x"]])
        y0 = float(first[idx["y"]])
        z0 = float(first[idx["z"]])
        q0 = normalize_quat(
            float(first[idx["qw"]]),
            float(first[idx["qx"]]),
            float(first[idx["qy"]]),
            float(first[idx["qz"]]),
        )
        q0c = quat_conj(q0)

        def rows():
            yield first
            for r in reader:
                yield r

        for r in rows():
            t = int(r[idx["t"]])
            x = float(r[idx["x"]])
            y = float(r[idx["y"]])
            z = float(r[idx["z"]])
            qi = normalize_quat(
                float(r[idx["qw"]]),
                float(r[idx["qx"]]),
                float(r[idx["qy"]]),
                float(r[idx["qz"]]),
            )
            q_rel = quat_mul(q0c, qi)
            yaw, pitch, roll = quat_to_euler_zyx_deg(q_rel)

            writer.writerow(
                [
                    f"{(t - t0) / 1e9:.9f}",
                    f"{x - x0:.9f}",
                    f"{y - y0:.9f}",
                    f"{z - z0:.9f}",
                    f"{pitch:.6f}",
                    f"{yaw:.6f}",
                    f"{roll:.6f}",
                ]
            )
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Convert BASALT trajectory.csv to relative time/xyz/pitch-yaw-roll CSV."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=Path(__file__).parent / "basalt" / "build" / "trajectory.csv",
        help="Path to BASALT trajectory.csv",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path(__file__).parent / "trajectory_postprocessed.csv",
        help="Path to output CSV",
    )
    args = parser.parse_args()

    if not args.input_csv.exists():
        raise FileNotFoundError(f"Input file not found: {args.input_csv}")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)

    n = process(args.input_csv, args.output_csv)
    print(f"Wrote {n} rows to: {args.output_csv}")


if __name__ == "__main__":
    main()

