"""Composite rendered embryo frames over the site's dark hero background."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


SITE_BG = np.array([6, 8, 15], dtype=np.float32)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames-dir", required=True)
    parser.add_argument("--poster", default="")
    parser.add_argument("--inner-radius", type=float, default=303.0)
    parser.add_argument("--outer-radius", type=float, default=326.0)
    return parser.parse_args()


def composite_image(path: Path, inner_radius: float, outer_radius: float) -> None:
    image = Image.open(path).convert("RGB")
    arr = np.asarray(image).astype(np.float32)
    height, width = arr.shape[:2]
    yy, xx = np.mgrid[:height, :width]
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    distance = np.sqrt((xx - center_x) ** 2 + (yy - center_y) ** 2)
    alpha = np.clip((distance - inner_radius) / (outer_radius - inner_radius), 0.0, 1.0)
    arr = arr * (1.0 - alpha[..., None]) + SITE_BG * alpha[..., None]
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB").save(path)


def main() -> None:
    args = parse_args()
    frames_dir = Path(args.frames_dir)
    for path in sorted(frames_dir.glob("embryo_hero_*.png")):
        composite_image(path, args.inner_radius, args.outer_radius)
    if args.poster:
        composite_image(Path(args.poster), args.inner_radius, args.outer_radius)


if __name__ == "__main__":
    main()
