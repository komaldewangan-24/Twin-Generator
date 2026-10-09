"""Convert a trained 3D Gaussian splat (.ply) into the compact .splat format.

Why: Brush writes the full training format (.ply, ~250 bytes per splat with
spherical-harmonic colour data), 100 to 200 MB for a room. The browser viewer
only needs position, size, colour, opacity and rotation (32 bytes per splat),
so converting makes the download about 8x smaller.

It also cleans the model. Training leaves "floaters": nearly transparent or
huge splats hanging in mid-air that look like fog in front of the camera. We
drop splats that are almost invisible, absurdly large, or far outside the room.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

SH_C0 = 0.28209479177387814  # zeroth-order spherical harmonic constant

_PLY_TYPES = {
    "float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8",
    "uchar": "u1", "uint8": "u1", "char": "i1", "int8": "i1",
    "ushort": "<u2", "uint16": "<u2", "short": "<i2", "int16": "<i2",
    "uint": "<u4", "uint32": "<u4", "int": "<i4", "int32": "<i4",
}


def _read_ply(path: Path) -> np.ndarray:
    with open(path, "rb") as f:
        if f.readline().strip() != b"ply":
            raise ValueError("not a PLY file")
        fmt = f.readline().decode().strip()
        if "binary_little_endian" not in fmt:
            raise ValueError("only binary little-endian PLY is supported")
        count, fields, in_vertex = 0, [], False
        while True:
            line = f.readline().decode().strip()
            if line == "end_header":
                break
            parts = line.split()
            if parts[:1] == ["element"]:
                in_vertex = parts[1] == "vertex"
                if in_vertex:
                    count = int(parts[2])
            elif parts[:1] == ["property"] and in_vertex:
                fields.append((parts[2], _PLY_TYPES[parts[1]]))
        data = np.fromfile(f, dtype=np.dtype(fields), count=count)
    if len(data) != count:
        raise ValueError("PLY file is truncated")
    return data


def ply_to_splat(
    ply_path: Path,
    out_path: Path,
    min_opacity: float = 0.05,
    max_scale_percentile: float = 99.5,
    max_distance_percentile: float = 99.0,
    max_count: int | None = 1_000_000,
) -> dict:
    """Write a cleaned .splat. Returns counts for logging."""
    d = _read_ply(ply_path)
    n = len(d)

    pos = np.stack([d["x"], d["y"], d["z"]], 1).astype(np.float32)
    scale = np.exp(np.stack([d["scale_0"], d["scale_1"], d["scale_2"]], 1)).astype(np.float32)
    opacity = 1.0 / (1.0 + np.exp(-d["opacity"].astype(np.float64)))
    rgb = 0.5 + SH_C0 * np.stack([d["f_dc_0"], d["f_dc_1"], d["f_dc_2"]], 1)
    quat = np.stack([d["rot_0"], d["rot_1"], d["rot_2"], d["rot_3"]], 1).astype(np.float64)
    quat /= np.maximum(np.linalg.norm(quat, axis=1, keepdims=True), 1e-9)

    biggest = scale.max(1)
    centre = np.median(pos, axis=0)
    dist = np.linalg.norm(pos - centre, axis=1)
    keep = (
        np.isfinite(pos).all(1)
        & (opacity >= min_opacity)
        & (biggest <= np.percentile(biggest, max_scale_percentile))
        & (dist <= np.percentile(dist, max_distance_percentile))
    )

    idx = np.flatnonzero(keep)
    # Most important first (large and opaque), so partial loads already look right.
    importance = scale[idx].prod(1) * opacity[idx]
    idx = idx[np.argsort(-importance)]
    if max_count and len(idx) > max_count:
        idx = idx[:max_count]  # a browser on a small GPU draws about a million splats comfortably

    rec = np.zeros(len(idx), dtype=[("p", "<f4", 3), ("s", "<f4", 3), ("c", "u1", 4), ("r", "u1", 4)])
    rec["p"] = pos[idx]
    rec["s"] = scale[idx]
    rec["c"] = np.concatenate([np.clip(rgb[idx] * 255, 0, 255), (opacity[idx] * 255)[:, None]], 1).astype(np.uint8)
    rec["r"] = np.clip(quat[idx] * 128 + 128, 0, 255).astype(np.uint8)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".splat.part")
    rec.tofile(tmp)
    tmp.replace(out_path)
    return {"in": n, "out": int(len(idx)), "mb": round(out_path.stat().st_size / 1e6, 1)}
