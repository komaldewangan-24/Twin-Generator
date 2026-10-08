from pathlib import Path

import cv2
import numpy as np


def make_contact_sheet(frames_dir: str, out_path: str, cols: int = 6, tile: int = 200, max_tiles: int = 48) -> str:
    """Combine a sample of frames into a grid collage used as the preview image."""
    frames = sorted(Path(frames_dir).glob("*.jpg"))
    if not frames:
        raise RuntimeError("no frames available for preview")

    step = max(1, len(frames) // max_tiles)
    chosen = frames[::step][:max_tiles]

    imgs: list[cv2.Mat] = []
    for path in chosen:
        img = cv2.imread(str(path))
        if img is not None:
            imgs.append(cv2.resize(img, (tile, tile)))

    if not imgs:
        raise RuntimeError("frames unreadable for preview")

    while len(imgs) < cols:
        imgs.append(imgs[-1])

    rows = [cv2.hconcat(imgs[i:i + cols]) for i in range(0, len(imgs), cols)]
    sheet = cv2.vconcat(rows)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet)
    return str(out)