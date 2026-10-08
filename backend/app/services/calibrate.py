"""Measurement calibration.

Splat world coordinates are in arbitrary units. This module converts them to
meters using a real-world reference. Two honest strategies:

1. Absolute (scene anchor): if the user knows a real distance in the scene
   (e.g. room width ~= 4m), the ratio real_meters / observed_units gives a scale.
2. Reference-object (auto): assume a standard indoor object height
   (chair seat ~= 0.45m). Works only when the splat preserves metric scale.

Because a monocular phone video has no intrinsic scale, results are always
reported as *estimates* — the API accepts an optional reference measurement.
"""

# Common real-world anchor, in meters
CHAIR_SEAT_M = 0.45
CHAIR_TOTAL_M = 0.90
DOOR_WIDTH_M = 0.85


def estimate_scale(observed_span_units: float, real_span_m: float) -> float:
    """meters-per-unit = real size / observed size.

    >>> estimate_scale(100, 4.0)
    0.04
    """
    if observed_span_units <= 0:
        raise ValueError("observed span must be positive")
    return real_span_m / observed_span_units


def observed_area_m2(observed_area_units2: float, scale: float) -> float:
    """Convert an area measured in arbitrary units^2 to m^2."""
    return observed_area_units2 * scale * scale


def compute_union_span(objects_xy: list[tuple[float, float]]) -> tuple[float, float, float]:
    """Bounding span of a set of (x, y) floor positions.

    Returns (max_dim, width, height) in the same units as the input.
    """
    if not objects_xy:
        return 0.0, 0.0, 0.0
    xs = [p[0] for p in objects_xy]
    ys = [p[1] for p in objects_xy]
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    return max(w, h), w, h