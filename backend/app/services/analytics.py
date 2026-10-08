import json

from app.models.project import Project
from app.services import calibrate, capacity, segment_rooms


def _load_detections(project: Project) -> dict:
    if not project.detections_json:
        return {"detections": []}
    return json.loads(project.detections_json)


def build_analytics(project: Project, room_width_m: float | None = None, room_height_m: float | None = None) -> dict:
    data = _load_detections(project)
    detections = data.get("detections", [])

    furniture = {d["class"]: d["count"] for d in detections}
    furniture_total = sum(furniture.values())

    positions = [(p["x"], p["z"]) for d in detections for p in d.get("positions", [])]

    rooms = segment_rooms.segment_rooms(positions[:300])

    capacity_calc = capacity.compute_capacity(detections)

    # Area estimate: bounding box of all object floor positions in scene units.
    unit_area = None
    bounds = None
    if positions:
        xs = [p[0] for p in positions]
        zs = [p[1] for p in positions]
        bounds = [min(xs), min(zs), max(xs), max(zs)]
        unit_area = round((max(xs) - min(xs)) * (max(zs) - min(zs)), 4)

    # Calibration (optional): user provides a known real-world span.
    calibration = None
    if room_width_m and bounds:
        observed_w = bounds[2] - bounds[0]
        if observed_w > 0:
            scale = calibrate.estimate_scale(observed_w, room_width_m)
            height_m = None
            if room_height_m and (bounds[3] - bounds[1]) > 0:
                height_m = calibrate.estimate_scale(bounds[3] - bounds[1], room_height_m)
            area_m2 = calibrate.observed_area_m2(unit_area, scale) if unit_area else None
            calibration = {
                "meters_per_unit": round(scale, 4),
                "area_m2": round(area_m2, 2) if area_m2 else None,
                "width_m": room_width_m,
                "height_m": round(height_m, 2) if height_m else None,
            }

    return {
        "rooms": {"count": rooms["count"], "details": rooms["rooms"]},
        "furniture": furniture,
        "furniture_total": furniture_total,
        "seating_capacity": capacity_calc,
        "area": {"unit_area": unit_area, "bounds": bounds, "calibration": calibration},
        "scan_date": project.scan_date.isoformat(),
    }