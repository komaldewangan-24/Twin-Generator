"""The real-world size of a scan.

A phone video has no absolute scale: the reconstruction is correct up to a constant, and the
pipeline guesses that constant from the camera height (about 1.4 m) and ceiling height (about 2.5 m).
A person can replace the guess with a measurement, either two points in the 3D view whose real
distance they know (a door frame, a sheet of A4, a tape measure laid on the floor) or the room's
real length. The result is stored with the scan, so the floor plan, analytics, assistant and PDF
all use it from then on.

The saved value is metres per reconstruction unit, not a ratio to the estimate, so it stays right
if the estimate is ever recomputed from the same reconstruction.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

# A measurement more than 4x away from the estimate is almost certainly two wrong points or a
# typing slip (cm instead of m), not a room that really is that different.
MIN_FACTOR, MAX_FACTOR = 0.25, 4.0
MIN_SEGMENT_M = 0.05


class ScaleError(ValueError):
    """The measurement cannot be used. The message tells the person what to check."""


def reconstruction(data: dict) -> dict | None:
    meta = data.get("meta") or {}
    recon = meta.get("reconstruction")
    return recon if meta.get("unit") == "m" and recon else None


def saved_meters_per_unit(data: dict) -> float | None:
    entry = (data.get("meta") or {}).get("user_scale")
    value = entry.get("meters_per_unit") if isinstance(entry, dict) else None
    return float(value) if isinstance(value, (int, float)) and math.isfinite(value) and value > 0 else None


def _entry(recon: dict, meters_per_unit: float, method: str, real_m: float, what: str) -> dict:
    factor = meters_per_unit / recon["meters_per_unit"]
    if not (MIN_FACTOR <= factor <= MAX_FACTOR):
        raise ScaleError(
            f"That {what} is {factor:.1f} times what the scan implies, which is too far off to be right. "
            "Check the two points you picked, and whether you typed metres."
        )
    return {
        "meters_per_unit": round(meters_per_unit, 6),
        "method": method,
        "real_m": round(real_m, 3),
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def from_points(recon: dict, a: list[float], b: list[float], real_m: float) -> dict:
    """Two points in the reconstruction's own coordinates whose true distance is `real_m`."""
    units = math.dist(a, b)
    estimated_m = units * recon["meters_per_unit"]
    if units <= 0 or estimated_m < MIN_SEGMENT_M:
        raise ScaleError("The two points are almost on top of each other. Pick two points further apart.")
    return _entry(recon, real_m / units, "points", real_m, f"length ({real_m:g} m against {estimated_m:.2f} m measured)")


def from_room(recon: dict, longer_m: float, shorter_m: float | None) -> dict:
    """The room's real longer side, and optionally its shorter side."""
    room = recon["room"]
    if room["width_m"] <= 0:
        raise ScaleError("This scan has no room outline to compare with.")
    factor = longer_m / room["width_m"]
    if shorter_m and room["depth_m"] > 0:
        factor = (factor * shorter_m / room["depth_m"]) ** 0.5
    return _entry(recon, recon["meters_per_unit"] * factor, "room", longer_m, "room size")


def save(data: dict, entry: dict | None) -> dict:
    """Store (or with None, forget) the person's calibration on the scan's data."""
    meta = data.setdefault("meta", {})
    if entry is None:
        meta.pop("user_scale", None)
    else:
        meta["user_scale"] = entry
    return data
