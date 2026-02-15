#!/usr/bin/env python3
"""
Export trajectory replay assets to frontend/public so the Replay tab can auto-load.
"""

import argparse
import json
import shutil
from pathlib import Path


def numeric_sort_key(name: str):
    stem = Path(name).stem
    return (0, int(stem)) if stem.isdigit() else (1, name.lower())


def export_assets(trajectory_csv: Path, images_dir: Path, replay_public_dir: Path) -> None:
    if not trajectory_csv.exists():
        raise FileNotFoundError(f"Trajectory CSV not found: {trajectory_csv}")
    if not images_dir.exists():
        raise FileNotFoundError(f"Images directory not found: {images_dir}")

    replay_public_dir.mkdir(parents=True, exist_ok=True)
    out_csv = replay_public_dir / "trajectory.csv"
    out_images = replay_public_dir / "images"
    manifest_path = replay_public_dir / "images_manifest.json"

    shutil.copy2(trajectory_csv, out_csv)

    if out_images.exists():
        shutil.rmtree(out_images)
    out_images.mkdir(parents=True, exist_ok=True)

    image_files = [p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    image_files.sort(key=lambda p: numeric_sort_key(p.name))

    manifest_names = []
    for p in image_files:
        dst = out_images / p.name
        shutil.copy2(p, dst)
        manifest_names.append(p.name)

    manifest_path.write_text(json.dumps({"images": manifest_names}, indent=2))

    print(f"Exported trajectory CSV: {out_csv}")
    print(f"Exported images: {len(manifest_names)} -> {out_images}")
    print(f"Wrote manifest: {manifest_path}")


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Export replay assets into frontend/public/replay.")
    parser.add_argument(
        "--trajectory-csv",
        type=Path,
        default=root / "trajectory_postprocessed.csv",
        help="Trajectory CSV to publish for replay",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=root / "trajectory_data" / "mav0" / "cam0" / "data",
        help="Directory containing replay images",
    )
    parser.add_argument(
        "--replay-public-dir",
        type=Path,
        default=root.parent / "frontend" / "public" / "replay",
        help="Output directory served by frontend as /replay",
    )
    args = parser.parse_args()

    export_assets(
        trajectory_csv=args.trajectory_csv.resolve(),
        images_dir=args.images_dir.resolve(),
        replay_public_dir=args.replay_public_dir.resolve(),
    )


if __name__ == "__main__":
    main()

