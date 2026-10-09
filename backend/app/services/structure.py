"""The 3D structure recovered from the video, as a point cloud the browser can draw.

Structure-from-motion does not only give camera positions: it triangulates thousands of real
points on walls, furniture and floor. Drawing them (with the room box, the camera path and the
detected objects) shows the 3D structure the app built from the video, independent of the
photoreal model, which needs a GPU trainer. This file is also what remains if training fails.

File format (little endian), small and trivial to read in JavaScript:
    4 bytes  magic  b"TWSP"
    4 bytes  uint32 point count n
    n * 3 float32   x, y, z   (the model's own coordinates, same as the 3D viewer)
    n * 3 uint8     r, g, b
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

MAGIC = b"TWSP"
MAX_POINTS = 60_000


def write_points(rec, path: Path, max_points: int = MAX_POINTS) -> int:
    """Write the sparse cloud. Drops the least reliable 10% (highest reprojection error)."""
    pts = list(rec.points3D.values())
    if not pts:
        raise ValueError("the reconstruction has no 3D points")
    errors = np.array([p.error for p in pts])
    keep = errors <= np.percentile(errors, 90)
    xyz = np.array([p.xyz for p, k in zip(pts, keep) if k], dtype="<f4")
    rgb = np.array([p.color for p, k in zip(pts, keep) if k], dtype="u1")
    if len(xyz) > max_points:
        idx = np.random.default_rng(0).choice(len(xyz), max_points, replace=False)
        xyz, rgb = xyz[idx], rgb[idx]
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    with open(tmp, "wb") as f:
        f.write(MAGIC + struct.pack("<I", len(xyz)))
        f.write(xyz.tobytes())
        f.write(rgb.tobytes())
    tmp.replace(path)
    return len(xyz)


def read_points(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = path.read_bytes()
    if data[:4] != MAGIC:
        raise ValueError("not a structure file")
    (n,) = struct.unpack("<I", data[4:8])
    xyz = np.frombuffer(data, dtype="<f4", count=n * 3, offset=8).reshape(n, 3)
    rgb = np.frombuffer(data, dtype="u1", count=n * 3, offset=8 + n * 12).reshape(n, 3)
    return xyz, rgb
