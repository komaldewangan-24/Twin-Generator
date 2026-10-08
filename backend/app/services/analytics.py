import json

from app.models.project import Project
from app.services import calibrate, capacity, segment_rooms


def _load_detections(project: Project) -> dict:
    if not project.detections_json:
        return {"detections": []}
    return json.loads(project.detections_json)


# Rough floor footprint of one object, in m². Used only to estimate empty floor space.
FOOTPRINT_M2 = {
    "chair": 0.2, "couch": 1.8, "dining table": 1.2, "bed": 2.2, "potted plant": 0.15, "tv": 0.15,
    "sink": 0.3, "refrigerator": 0.45, "bench": 0.5, "microwave": 0.1, "oven": 0.4, "toilet": 0.3,
    "counter": 0.9, "cabinet": 0.4, "shelf": 0.3,
}
ZONE_RADIUS_M = 1.8  # furniture closer than this belongs to the same zone


def build_analytics(project: Project, room_width_m: float | None = None, room_height_m: float | None = None) -> dict:
    data = _load_detections(project)
    if data.get("meta", {}).get("unit") == "m" and data["meta"].get("reconstruction"):
        return _build_metric(project, data, room_width_m, room_height_m)
    return _build_view(project, data, room_width_m, room_height_m)


def _build_metric(project: Project, data: dict, room_width_m: float | None, room_depth_m: float | None) -> dict:
    """Analytics when objects were placed in real 3D (positions are in metres)."""
    detections = data.get("detections", [])
    recon = data["meta"]["reconstruction"]
    room = recon["room"]

    # The scale is an assumption (phone held at ~1.4 m). A tape measure beats it.
    factor = 1.0
    source = "estimated"
    if room_width_m and room["width_m"] > 0:
        factor = room_width_m / room["width_m"]
        source = "user"
        if room_depth_m and room["depth_m"] > 0:
            factor = (factor * (room_depth_m / room["depth_m"])) ** 0.5

    furniture = {d["class"]: d["count"] for d in detections}
    positions = [(p["x"] * factor, p["z"] * factor) for d in detections for p in d.get("positions", [])]
    rooms = segment_rooms.segment_rooms(positions[:300], eps=ZONE_RADIUS_M)

    width, depth = room["width_m"] * factor, room["depth_m"] * factor
    area = room["area_m2"] * factor * factor
    footprint = sum(FOOTPRINT_M2.get(d["class"], 0.0) * d["count"] for d in detections)
    free = max(area - footprint, 0.0)

    return {
        "rooms": {"count": rooms["count"], "details": rooms["rooms"]},
        "furniture": furniture,
        "furniture_total": sum(furniture.values()),
        "seating_capacity": capacity.compute_capacity(detections),
        "area": {
            "unit_area": None,
            "bounds": None,
            "calibration": {
                "meters_per_unit": round(recon["meters_per_unit"] * factor, 5),
                "area_m2": round(area, 1),
                "width_m": round(width, 2),
                "height_m": round(depth, 2),
                "source": source,
                "method": recon["scale_method"],
            },
        },
        "layout": {
            "unit": "m",
            "scale_factor": round(factor, 4),
            "width_m": round(width, 2),
            "depth_m": round(depth, 2),
            "area_m2": round(area, 1),
            "ceiling_height_m": round(room["ceiling_height_m"] * factor, 2),
            "polygon": [[x * factor, z * factor] for x, z in room["polygon"]],
            "camera_path": [[x * factor, z * factor] for x, z in recon["camera_path"]],
            "notes": recon.get("notes", []),
            "source": source,
        },
        "empty_space": {
            "free_m2": round(free, 1),
            "percent": round(100 * free / area) if area > 0 else None,
            "note": "Estimated from typical furniture sizes",
        },
        "scan_date": project.scan_date.isoformat(),
    }


def _build_view(project: Project, data: dict, room_width_m: float | None, room_height_m: float | None) -> dict:
    """Fallback analytics: positions are in normalised camera-view units."""
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

    # Calibration (optional): user provides a known real-world width, and
    # optionally the depth (far-to-near distance) of the scanned area.
    calibration = None
    if room_width_m and bounds:
        observed_w = bounds[2] - bounds[0]
        if observed_w > 0:
            scale = calibrate.estimate_scale(observed_w, room_width_m)
            if room_height_m:
                # Both sides known: the area is simply width x depth.
                area_m2 = room_width_m * room_height_m
            else:
                area_m2 = calibrate.observed_area_m2(unit_area, scale) if unit_area else None
            calibration = {
                "meters_per_unit": round(scale, 4),
                "area_m2": round(area_m2, 2) if area_m2 else None,
                "width_m": room_width_m,
                "height_m": room_height_m or None,
            }

    return {
        "rooms": {"count": rooms["count"], "details": rooms["rooms"]},
        "furniture": furniture,
        "furniture_total": furniture_total,
        "seating_capacity": capacity_calc,
        "area": {"unit_area": unit_area, "bounds": bounds, "calibration": calibration},
        "scan_date": project.scan_date.isoformat(),
    }