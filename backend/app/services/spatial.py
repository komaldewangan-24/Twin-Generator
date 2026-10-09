"""Put 2D detections into real 3D space, using the camera poses from SfM.

Why this exists: a detection box only says where an object is *in one photo*.
The same chair seen from two angles lands in two different places on screen,
so counting by screen position over- or under-counts and the "floor plan" is
just the camera view. With camera poses we can instead work out where each
object stands on the floor, merge sightings of the same object from different
frames, and read off real room dimensions.

Scale: structure-from-motion has no absolute scale. We assume the phone was
held at a typical standing height (1.4 m by default) and cross-check it
against a typical ceiling height. Both are *assumptions*, so results are
labelled as estimates and the user can override them with a tape measure.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import cv2
import numpy as np

# numpy on Apple's Accelerate library raises spurious FP-flag warnings from matmul
# even when every value is finite. Real problems are caught by the isfinite checks below.
warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)

ASSUMED_CAMERA_HEIGHT_M = 1.4
ASSUMED_CEILING_HEIGHT_M = 2.5

# Objects that stand on the floor: their box bottom can be projected onto it.
FLOOR_STANDING = {
    "chair", "couch", "dining table", "bed", "potted plant", "refrigerator",
    "bench", "toilet", "oven", "door", "counter", "cabinet", "shelf",
}

# How far apart (metres) two sightings must be to count as different objects.
MERGE_RADIUS_M = {
    "chair": 0.35, "couch": 0.9, "dining table": 0.7, "bed": 1.0, "potted plant": 0.3,
    "tv": 0.5, "sink": 0.4, "refrigerator": 0.5, "bench": 0.6, "door": 0.9,
    "window": 1.2, "light": 0.7, "counter": 0.9, "cabinet": 0.6, "shelf": 0.6,
}
DEFAULT_MERGE_RADIUS_M = 0.5

MIN_VOTES = 2  # an object must be seen in at least this many frames
# The open-vocabulary model is less certain than the standard one (it will call a box on a table a
# cabinet in a frame or two), so what it finds must stay in view for longer to count.
MIN_VOTES_BY_CLASS = {
    "door": 3, "window": 3, "light": 4, "counter": 4, "cabinet": 4, "shelf": 4, "picture": 4, "curtain": 4,
}

# Classes that rarely appear in an ordinary room and are easily confused with other things
# (a striped rug looks like a bench, a bean bag like a toilet) must score higher on average.
# Real ones usually do. Everything else only needs the detector's own threshold.
MIN_CONFIDENCE = {
    "toilet": 0.70, "bench": 0.65, "sink": 0.60, "refrigerator": 0.55, "oven": 0.60, "microwave": 0.60,
}


@dataclass
class Scene:
    up: np.ndarray
    e1: np.ndarray
    e2: np.ndarray
    floor_h: float
    ceiling_h: float
    meters_per_unit: float
    scale_method: str
    origin_uv: tuple[float, float]           # (u_min, v_min) of the footprint, in SfM units
    footprint_m: list[list[float]]           # hull polygon, metres, origin at footprint corner
    width_m: float
    depth_m: float
    area_m2: float
    ceiling_height_m: float
    camera_path_m: list[list[float]]
    start_view: dict = field(default_factory=dict)   # a real camera pose, in SfM world coordinates
    room_box: dict = field(default_factory=dict)     # floor and ceiling outlines in SfM world coordinates, for the 3D structure view
    tour: list = field(default_factory=list)         # camera poses in filming order, for the guided walkthrough
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "up": [round(float(v), 4) for v in self.up],
            "meters_per_unit": round(self.meters_per_unit, 5),
            "scale_method": self.scale_method,
            "assumed_camera_height_m": ASSUMED_CAMERA_HEIGHT_M,
            "room": {
                "width_m": round(self.width_m, 2),
                "depth_m": round(self.depth_m, 2),
                "area_m2": round(self.area_m2, 1),
                "ceiling_height_m": round(self.ceiling_height_m, 2),
                "polygon": [[round(x, 2), round(z, 2)] for x, z in self.footprint_m],
            },
            "camera_path": [[round(x, 2), round(z, 2)] for x, z in self.camera_path_m],
            "start_view": self.start_view,
            "room_box": self.room_box,
            "tour": self.tour,
            "notes": self.notes,
        }


# --------------------------------------------------------------------------- scene


def _snap_to_horizontal_plane(pts: np.ndarray, up: np.ndarray, max_angle_deg: float = 25.0, trials: int = 800):
    """Refine `up` using RANSAC planes: the largest plane whose normal lies within
    `max_angle_deg` of the guess is almost certainly the floor or ceiling."""
    rng = np.random.default_rng(0)
    extent = np.percentile(pts, 95, axis=0) - np.percentile(pts, 5, axis=0)
    tol = 0.012 * float(np.linalg.norm(extent))
    cos_min = np.cos(np.radians(max_angle_deg))
    remaining = pts
    best_n, best_inl = None, 0
    for _ in range(6):  # peel off the six biggest planes
        if len(remaining) < 100:
            break
        top = None
        for _ in range(trials):
            a, b, c = remaining[rng.choice(len(remaining), 3, replace=False)]
            n = np.cross(b - a, c - a)
            norm = np.linalg.norm(n)
            if norm < 1e-12:
                continue
            n /= norm
            inl = int((np.abs((remaining - a) @ n) < tol).sum())
            if top is None or inl > top[0]:
                top = (inl, n, a)
        if top is None:
            break
        inl, n, a = top
        if abs(float(n @ up)) >= cos_min and inl > best_inl and inl >= 0.04 * len(pts):
            best_n, best_inl = n if n @ up > 0 else -n, inl
        remaining = remaining[np.abs((remaining - a) @ n) >= tol]
    if best_n is None:
        return up, False
    return best_n, True


def _rot(image) -> np.ndarray:
    return np.array(image.cam_from_world().matrix())[:, :3]


def build_scene(rec) -> Scene:
    """Work out which way is up, where the floor is, and the room's size."""
    images = [im for im in rec.images.values() if im.has_pose]
    if len(images) < 5 or len(rec.points3D) < 50:
        raise ValueError("not enough reconstructed geometry")

    # Which way is up? Start from the cameras: a handheld phone's own "up"
    # (COLMAP camera -y axis) points roughly up, so the average over all frames
    # is a first guess. It is off by the typical tilt, so the guess is then
    # snapped to the nearest big flat surface (floor or ceiling) of the room.
    cam_ups = np.array([_rot(im).T @ np.array([0.0, -1.0, 0.0]) for im in images])
    mean_up = cam_ups.mean(0)
    agreement = float(np.linalg.norm(mean_up))
    up = mean_up / max(agreement, 1e-9)

    notes = []
    if agreement < 0.6:  # camera ups all over the place: portrait/landscape mixed, or rolled a lot
        notes.append("The phone was rotated a lot while filming, so floor and size estimates may be less accurate.")

    pts = np.array([p.xyz for p in rec.points3D.values()])
    errs = np.array([p.error for p in rec.points3D.values()])
    pts = pts[errs <= np.percentile(errs, 90)]  # drop the sloppiest 10 %
    up, snapped = _snap_to_horizontal_plane(pts, up)
    if not snapped:
        notes.append("No clear floor or ceiling was found, so 'up' comes from the camera tilt alone.")

    if not (np.isfinite(pts).all() and np.isfinite(up).all()):
        raise ValueError("reconstruction contains invalid numbers")
    h = pts @ up
    cam_c = np.array([im.projection_center() for im in images])
    cam_h = cam_c @ up

    floor_h = float(np.percentile(h, 4))
    ceiling_h = float(np.percentile(h, 96))
    # The camera cannot be below the floor: if the estimate says so, the floor
    # is actually lower than the points we saw (e.g. featureless carpet).
    if floor_h >= float(np.percentile(cam_h, 5)):
        floor_h = float(np.percentile(cam_h, 5)) - 0.3 * max(ceiling_h - floor_h, 1e-3)
        notes.append("Floor had few features; its height is a rough guess.")

    cam_above = float(np.median(cam_h) - floor_h)
    room_units = max(ceiling_h - floor_h, 1e-6)
    scale_cam = ASSUMED_CAMERA_HEIGHT_M / max(cam_above, 1e-6)
    scale_room = ASSUMED_CEILING_HEIGHT_M / room_units
    ratio = max(scale_cam, scale_room) / min(scale_cam, scale_room)
    if ratio < 1.5:
        scale = float(np.sqrt(scale_cam * scale_room))
        method = "camera height and ceiling height (both assumed)"
    else:
        scale = scale_cam
        method = "camera height (assumed 1.4 m)"
        notes.append("Room height did not match a typical ceiling, so scale uses camera height only.")

    # Floor axes: align with the dominant direction of the room (walls are
    # usually axis-aligned), found by PCA of the points between floor and ceiling.
    helper = np.array([1.0, 0, 0]) if abs(up[0]) < 0.9 else np.array([0, 1.0, 0])
    a = np.cross(up, helper)
    a /= np.linalg.norm(a)
    b = np.cross(up, a)
    band = (h > floor_h + 0.1 * room_units) & (h < ceiling_h - 0.1 * room_units)
    wall_pts = pts[band] if band.sum() > 50 else pts
    xy = np.stack([wall_pts @ a, wall_pts @ b], 1)
    cov = np.cov((xy - xy.mean(0)).T)
    evals, evecs = np.linalg.eigh(cov)
    major = evecs[:, int(np.argmax(evals))]
    e1 = major[0] * a + major[1] * b
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(up, e1)

    u = wall_pts @ e1
    v = wall_pts @ e2
    u_lo, u_hi = np.percentile(u, [2, 98])
    v_lo, v_hi = np.percentile(v, [2, 98])
    trimmed = np.stack([u, v], 1)[(u >= u_lo) & (u <= u_hi) & (v >= v_lo) & (v <= v_hi)]
    hull = cv2.convexHull(((trimmed - [u_lo, v_lo]) * scale).astype(np.float32)).reshape(-1, 2)
    area = float(cv2.contourArea(hull))
    cam_uv = np.stack([cam_c @ e1, cam_c @ e2], 1)
    path = (cam_uv - [u_lo, v_lo]) * scale

    # The room as a 3D box in the model's own coordinates: the floor outline at floor height and
    # the same outline at ceiling height. The structure view draws it as walls.
    hull_uv = hull / scale + np.array([u_lo, v_lo])
    def _lift(height: float) -> list[list[float]]:
        return [
            [round(float(v), 4) for v in (u * e1 + w * e2 + height * up)]
            for u, w in hull_uv
        ]
    room_box = {"floor": _lift(floor_h), "ceiling": _lift(ceiling_h)}

    # An implausibly small/large room means the scale assumption failed.
    width, depth = (u_hi - u_lo) * scale, (v_hi - v_lo) * scale
    if max(width, depth) > 40 or min(width, depth) < 0.8:
        notes.append("Room size looks unusual; enter a measured width on the Analytics tab to correct it.")

    # A good first view for the 3D viewer: the camera closest to the middle of the
    # walk, looking the way the phone looked. It sits inside the room and shows
    # what a photo of the room looks like.
    mid = int(np.argmin(np.linalg.norm(cam_c - np.median(cam_c, axis=0), axis=1)))
    fwd = _rot(images[mid]).T @ np.array([0.0, 0.0, 1.0])
    start_view = {
        "position": [round(float(v), 4) for v in cam_c[mid]],
        "forward": [round(float(v), 4) for v in fwd / np.linalg.norm(fwd)],
    }

    # Guided walkthrough: replay the walk using the real camera poses, in filming order.
    ordered = sorted(images, key=lambda im: im.name)
    stride = max(1, len(ordered) // 60)
    tour = []
    for im in ordered[::stride]:
        f = _rot(im).T @ np.array([0.0, 0.0, 1.0])
        tour.append({
            "position": [round(float(v), 4) for v in im.projection_center()],
            "forward": [round(float(v), 4) for v in f / np.linalg.norm(f)],
        })

    return Scene(
        up=up, e1=e1, e2=e2, floor_h=floor_h, ceiling_h=ceiling_h,
        meters_per_unit=scale, scale_method=method,
        origin_uv=(float(u_lo), float(v_lo)),
        footprint_m=hull.tolist(), width_m=float(width), depth_m=float(depth), area_m2=area,
        ceiling_height_m=float(room_units * scale),
        camera_path_m=path[:: max(1, len(path) // 80)].tolist(),
        start_view=start_view,
        room_box=room_box,
        tour=tour,
        notes=notes,
    )


# --------------------------------------------------------------------------- locating


def _inside(pt, box, shrink=0.12) -> bool:
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    return (x1 + shrink * w <= pt[0] <= x2 - shrink * w) and (y1 + shrink * h <= pt[1] <= y2 - shrink * h)


def locate(image, camera, rec, scene: Scene, cls: str, box) -> tuple[float, float, str, np.ndarray] | None:
    """Floor position (u, v) in SfM units for a box in `image`, plus the 3D point
    in SfM world coordinates (the same frame as the 3D model), or None."""
    pts = []
    for p2 in image.points2D:
        if p2.has_point3D() and _inside(p2.xy, box):
            pts.append(rec.points3D[p2.point3D_id].xyz)
    if len(pts) >= 4:
        c = np.median(np.array(pts), axis=0)
        return float(c @ scene.e1), float(c @ scene.e2), "points", c

    # Few features on the object (plain sofa, glossy table): fall back to where
    # the bottom of the box meets the floor.
    if cls in FLOOR_STANDING and box[3] < camera.height - 3:
        foot = np.array([(box[0] + box[2]) / 2, box[3]])
        ray_cam = np.append(camera.cam_from_img(foot), 1.0)
        R = _rot(image)
        d = R.T @ ray_cam
        d /= np.linalg.norm(d)
        C = np.array(image.projection_center())
        denom = float(d @ scene.up)
        if denom < -1e-3:
            t = (scene.floor_h - float(C @ scene.up)) / denom
            if 0 < t < 60 * (scene.ceiling_h - scene.floor_h):
                p = C + t * d
                return float(p @ scene.e1), float(p @ scene.e2), "floor", p

    # Featureless and not on the floor (a black TV screen, a window, a picture):
    # borrow the depth of the features just around the box. Walls and desks next
    # to the object are at about the same distance from the camera.
    x1, y1, x2, y2 = box
    cx, cy, w, h = (x1 + x2) / 2, (y1 + y2) / 2, (x2 - x1) * 1.7, (y2 - y1) * 1.7
    ring = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    M = np.array(image.cam_from_world().matrix())
    depths = [
        float(M[2, :3] @ rec.points3D[p2.point3D_id].xyz + M[2, 3])
        for p2 in image.points2D
        if p2.has_point3D() and _inside(p2.xy, ring, shrink=0.0)
    ]
    depths = [d for d in depths if d > 0]
    if len(depths) >= 8:
        depth = float(np.median(depths))
        p_cam = np.append(camera.cam_from_img(np.array([cx, cy])), 1.0) * depth
        p = M[:, :3].T @ (p_cam - M[:, 3])
        return float(p @ scene.e1), float(p @ scene.e2), "neighbours", p
    return None


# --------------------------------------------------------------------------- merging


def merge_observations(observations: list[dict], scene: Scene) -> list[dict]:
    """Merge sightings of the same object across frames.

    observations: [{cls, u, v, conf, frame}] with u, v in SfM units.
    Returns one dict per physical object, positions in metres.
    """
    scale = scene.meters_per_unit
    u0, v0 = scene.origin_uv
    by_cls: dict[str, list[dict]] = {}
    for o in observations:
        by_cls.setdefault(o["cls"], []).append(o)

    objects = []
    for cls, obs in by_cls.items():
        radius = MERGE_RADIUS_M.get(cls, DEFAULT_MERGE_RADIUS_M) / scale
        clusters: list[dict] = []
        for o in sorted(obs, key=lambda o: -o["conf"]):
            best, best_d = None, radius
            for c in clusters:
                d = float(np.hypot(c["u"] - o["u"], c["v"] - o["v"]))
                if d < best_d:
                    best, best_d = c, d
            if best is None:
                clusters.append({"u": o["u"], "v": o["v"], "w": o["conf"], "confs": [o["conf"]], "frames": {o["frame"]},
                                 "world": np.array(o["world"], dtype=float) * o["conf"] if o.get("world") is not None else None})
            else:
                w = best["w"] + o["conf"]
                best["u"] = (best["u"] * best["w"] + o["u"] * o["conf"]) / w
                best["v"] = (best["v"] * best["w"] + o["v"] * o["conf"]) / w
                if o.get("world") is not None:
                    add = np.array(o["world"], dtype=float) * o["conf"]
                    best["world"] = add if best["world"] is None else best["world"] + add
                best["w"] = w
                best["confs"].append(o["conf"])
                best["frames"].add(o["frame"])
        for c in clusters:
            if len(c["frames"]) >= MIN_VOTES_BY_CLASS.get(cls, MIN_VOTES) and float(np.mean(c["confs"])) >= MIN_CONFIDENCE.get(cls, 0.0):
                objects.append({
                    "class": cls,
                    "x": (c["u"] - u0) * scale,
                    "z": (c["v"] - v0) * scale,
                    "confidence": float(np.mean(c["confs"])),
                    "votes": len(c["frames"]),
                    # weighted mean 3D point, in the 3D model's own coordinates
                    "world": (c["world"] / c["w"]).round(4).tolist() if c["world"] is not None else None,
                })
    return objects
