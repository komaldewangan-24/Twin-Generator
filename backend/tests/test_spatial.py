"""Spatial grounding against a synthetic room with known size.

We build a 5 x 4 x 2.5 m room, scatter 'SfM points' on its surfaces, put 40
cameras at 1.4 m, then rotate everything randomly and shrink it by an arbitrary
scale, just like real structure-from-motion output (arbitrary frame, arbitrary
scale). build_scene must recover up, floor, size and scale.
"""

import numpy as np
import pytest

from app.services import spatial

ROOM = (5.0, 4.0, 2.5)  # x, y, z(up) in metres
SFM_SCALE = 0.37        # SfM has no absolute scale


class _Rigid:
    def __init__(self, R, t):
        self._m = np.hstack([R, t[:, None]])

    def matrix(self):
        return self._m


class _Image:
    has_pose = True

    def __init__(self, R_cw, center, name):
        self.R, self.C, self.name = R_cw, center, name

    def cam_from_world(self):
        return _Rigid(self.R, -self.R @ self.C)

    def projection_center(self):
        return self.C


class _Point:
    def __init__(self, xyz):
        self.xyz, self.error, self.color = xyz, 0.5, np.array([200, 120, 40], dtype="u1")


class _Rec:
    def __init__(self, images, points):
        self.images = dict(enumerate(images))
        self.points3D = dict(enumerate(points))


def _rotation(rng):
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    return q if np.linalg.det(q) > 0 else -q


def make_reconstruction(seed=0):
    rng = np.random.default_rng(seed)
    W, D, H = ROOM
    n = 800
    surfaces = [
        np.c_[rng.uniform(0, W, n), rng.uniform(0, D, n), np.zeros(n)],          # floor
        np.c_[rng.uniform(0, W, n), rng.uniform(0, D, n), np.full(n, H)],        # ceiling
        np.c_[rng.uniform(0, W, n), np.zeros(n), rng.uniform(0, H, n)],          # walls
        np.c_[rng.uniform(0, W, n), np.full(n, D), rng.uniform(0, H, n)],
        np.c_[np.zeros(n), rng.uniform(0, D, n), rng.uniform(0, H, n)],
        np.c_[np.full(n, W), rng.uniform(0, D, n), rng.uniform(0, H, n)],
    ]
    pts = np.concatenate(surfaces) + rng.normal(0, 0.01, (6 * n, 3))

    Q = _rotation(rng)          # unknown world orientation
    up_true = Q @ np.array([0.0, 0.0, 1.0])
    images = []
    for i in range(40):
        c = np.array([rng.uniform(0.8, W - 0.8), rng.uniform(0.8, D - 0.8), 1.4 + rng.normal(0, 0.05)])
        yaw, pitch = rng.uniform(0, 2 * np.pi), np.radians(rng.uniform(-25, 25))
        fwd = np.array([np.cos(yaw) * np.cos(pitch), np.sin(yaw) * np.cos(pitch), np.sin(pitch)])
        right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right)
        down = np.cross(fwd, right)  # COLMAP: x right, y down, z forward
        R_room = np.stack([right, down, fwd])          # camera-from-room rotation
        R_cw = R_room @ Q.T                            # camera-from-(rotated)world
        images.append(_Image(R_cw, SFM_SCALE * (Q @ c), f"f{i}.jpg"))
    points = [_Point(SFM_SCALE * (Q @ p)) for p in pts]
    return _Rec(images, points), up_true


def test_build_scene_recovers_up_size_and_scale():
    rec, up_true = make_reconstruction()
    scene = spatial.build_scene(rec)

    angle = np.degrees(np.arccos(np.clip(scene.up @ up_true, -1, 1)))
    assert angle < 4, f"up is off by {angle:.1f} degrees"

    long_side, short_side = sorted([scene.width_m, scene.depth_m], reverse=True)
    assert 4.0 < long_side < 6.0
    assert 3.2 < short_side < 5.0
    assert 2.0 < scene.ceiling_height_m < 3.0
    # meters_per_unit * SFM_SCALE should be ~1 (SfM unit -> metre round trip)
    assert 0.85 < scene.meters_per_unit * SFM_SCALE < 1.15


def test_merge_counts_distinct_objects_and_drops_one_off_sightings():
    rec, _ = make_reconstruction()
    scene = spatial.build_scene(rec)
    m = SFM_SCALE ** -1  # SfM units per metre, roughly

    def obs(cls, u_m, v_m, frame, conf=0.8):
        return {"cls": cls, "u": scene.origin_uv[0] + u_m / scene.meters_per_unit,
                "v": scene.origin_uv[1] + v_m / scene.meters_per_unit, "conf": conf, "frame": frame}

    observations = [
        # one chair seen in three frames, slightly different estimates
        obs("chair", 1.00, 1.00, "a"), obs("chair", 1.05, 0.98, "b"), obs("chair", 0.97, 1.03, "c"),
        # a second chair 1.2 m away, seen twice
        obs("chair", 2.20, 1.00, "a"), obs("chair", 2.18, 1.04, "d"),
        # a false alarm seen in a single frame
        obs("couch", 3.00, 3.00, "e"),
    ]
    merged = spatial.merge_observations(observations, scene)
    chairs = [o for o in merged if o["class"] == "chair"]
    assert len(chairs) == 2
    assert not any(o["class"] == "couch" for o in merged)
    assert sorted(o["votes"] for o in chairs) == [2, 3]
    xs = sorted(o["x"] for o in chairs)
    assert abs((xs[1] - xs[0]) - 1.2) < 0.15


def test_merged_objects_carry_their_3d_position_for_the_viewer():
    """Pins and 'show in 3D' need each object's position in the 3D model's own
    coordinates. Merging sightings must average them, weighted by confidence."""
    rec, _ = make_reconstruction()
    scene = spatial.build_scene(rec)

    def obs(frame, world, conf):
        return {"cls": "tv", "u": 1.0, "v": 1.0, "conf": conf, "frame": frame, "world": world}

    merged = spatial.merge_observations(
        [obs("a", [1.0, 2.0, 3.0], 0.5), obs("b", [3.0, 2.0, 5.0], 0.5), obs("c", [2.0, 2.0, 4.0], 0.5)], scene
    )
    assert len(merged) == 1
    assert merged[0]["world"] == pytest.approx([2.0, 2.0, 4.0], abs=1e-3)


def test_scene_exports_a_walkthrough_path_and_start_view():
    rec, _ = make_reconstruction()
    scene = spatial.build_scene(rec).to_json()
    assert 2 <= len(scene["tour"]) <= 70
    for pose in scene["tour"]:
        assert len(pose["position"]) == 3 and len(pose["forward"]) == 3
        assert abs(sum(v * v for v in pose["forward"]) - 1) < 1e-2   # unit direction
    assert set(scene["start_view"]) == {"position", "forward"}


def test_implausible_classes_need_stronger_evidence():
    """A bean bag mislabelled 'toilet' at ~0.56 must not become an object, while a chair at the
    same confidence (a normal furniture class) stays."""
    rec, _ = make_reconstruction()
    scene = spatial.build_scene(rec)

    def sightings(cls, conf):
        return [{"cls": cls, "u": 1.0, "v": 1.0, "conf": conf, "frame": f, "world": [0, 0, 0]} for f in "abc"]

    merged = spatial.merge_observations(sightings("toilet", 0.56) + sightings("chair", 0.56), scene)
    assert {o["class"] for o in merged} == {"chair"}
    assert {o["class"] for o in spatial.merge_observations(sightings("toilet", 0.85), scene)} == {"toilet"}


def test_room_box_is_a_flat_floor_and_a_flat_ceiling_above_it():
    """The structure view draws walls from these outlines, in the 3D model's own coordinates."""
    rec, up_true = make_reconstruction()
    scene = spatial.build_scene(rec)
    box = spatial.build_scene(rec).to_json()["room_box"]
    floor, ceiling = np.array(box["floor"]), np.array(box["ceiling"])
    assert len(floor) == len(ceiling) >= 3
    fh, ch = floor @ scene.up, ceiling @ scene.up
    assert np.ptp(fh) < 1e-2 and np.ptp(ch) < 1e-2, "each outline lies in one horizontal plane"
    height_m = (ch.mean() - fh.mean()) * scene.meters_per_unit
    assert 2.0 < height_m < 3.0, height_m
    # the outline surrounds the cameras: every camera is inside the floor polygon's bounding box
    cams = np.array([im.projection_center() for im in rec.images.values()])
    along = lambda pts, axis: pts @ axis
    for axis in (scene.e1, scene.e2):
        assert along(floor, axis).min() <= along(cams, axis).min() + 1e-3
        assert along(floor, axis).max() >= along(cams, axis).max() - 1e-3


def test_open_vocabulary_classes_must_stay_in_view_longer():
    """The open-vocabulary model calls a box on a table a cabinet now and then: a couple of frames
    must not be enough, while a chair (standard model) still needs only two."""
    rec, _ = make_reconstruction()
    scene = spatial.build_scene(rec)

    def sightings(cls, frames, u=1.0):
        return [{"cls": cls, "u": u, "v": 1.0, "conf": 0.6, "frame": f, "world": [0, 0, 0]} for f in frames]

    kept = lambda obs: {o["class"] for o in spatial.merge_observations(obs, scene)}  # noqa: E731
    assert kept(sightings("chair", "ab")) == {"chair"}
    assert kept(sightings("cabinet", "abc")) == set()
    assert kept(sightings("cabinet", "abcd")) == {"cabinet"}
    assert kept(sightings("door", "abc")) == {"door"}
    assert kept(sightings("window", "ab")) == set()


def test_one_wide_window_seen_from_different_angles_is_one_window():
    """Estimates of a window's centre scatter by half a metre or more between frames; two sightings
    a metre apart on the same wall are the same window, not two."""
    rec, _ = make_reconstruction()
    scene = spatial.build_scene(rec)
    u0, v0 = scene.origin_uv
    per_m = 1 / scene.meters_per_unit

    def sighting(frame, along_m):
        return {"cls": "window", "u": u0 + along_m * per_m, "v": v0, "conf": 0.5, "frame": frame, "world": [0, 0, 0]}

    near = [sighting(f, a) for f, a in zip("abcd", (1.0, 1.4, 1.8, 2.0))]
    assert len(spatial.merge_observations(near, scene)) == 1
    far = near + [sighting(f, 4.5) for f in "efgh"]            # a second window across the room
    assert len(spatial.merge_observations(far, scene)) == 2
