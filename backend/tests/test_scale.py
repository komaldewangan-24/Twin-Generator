"""Measuring in the 3D view and correcting the scale: the saved measurement reaches every consumer."""

import json
import math
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.project import Project
from app.services import chat, scale

RECON = {
    "meters_per_unit": 0.5,           # the estimate: one reconstruction unit is half a metre
    "scale_method": "camera-height",
    "up": [0, 1, 0],
    "room": {"width_m": 4.0, "depth_m": 3.0, "area_m2": 12.0, "ceiling_height_m": 2.5, "polygon": [[0, 0], [4, 0], [4, 3], [0, 3]]},
    "camera_path": [[1, 1], [2, 2]],
}
SCAN = {
    "detections": [
        {"class": "chair", "count": 1, "positions": [{"x": 1.0, "z": 1.0, "confidence": 0.9}]},
        {"class": "door", "count": 1, "positions": [{"x": 0.2, "z": 1.5, "confidence": 0.3}]},
    ],
    "meta": {"unit": "m", "reconstruction": RECON},
}


@pytest.fixture()
def api():
    with TestClient(app) as client:
        token = client.post("/auth/signup", json={"email": f"scale-{uuid.uuid4().hex[:8]}@example.com", "password": "secret123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        pid = client.post("/projects", json={"name": "Measured room"}, headers=headers).json()["id"]
        with SessionLocal() as db:
            db.get(Project, pid).detections_json = json.dumps(SCAN)
            db.commit()
        yield client, headers, pid


def test_two_points_set_the_scale_and_everything_follows(api):
    client, headers, pid = api
    before = client.get(f"/projects/{pid}/analytics", headers=headers).json()["layout"]
    assert before["source"] == "estimated" and before["measured"] is None and before["scale_factor"] == 1.0

    # 2.0 reconstruction units apart, truly 1.5 m: one unit is 0.75 m, not the estimated 0.5 m
    r = client.post(f"/projects/{pid}/calibrate", json={"a": [0, 0, 0], "b": [2, 0, 0], "real_m": 1.5}, headers=headers)
    assert r.status_code == 200, r.text
    layout = r.json()["layout"]
    assert layout["meters_per_unit"] == pytest.approx(0.75)
    assert layout["scale_factor"] == pytest.approx(1.5)
    assert layout["width_m"] == pytest.approx(6.0) and layout["depth_m"] == pytest.approx(4.5)
    assert layout["source"] == "user" and layout["measured"]["method"] == "points"

    # it is stored, so a fresh request, the assistant and the PDF's analytics see the same
    again = client.get(f"/projects/{pid}/analytics", headers=headers).json()["layout"]
    assert again["width_m"] == pytest.approx(6.0)
    with SessionLocal() as db:
        project = db.get(Project, pid)
        analytics = client.get(f"/projects/{pid}/analytics", headers=headers).json()
        said = chat.answer("where is the chair?", project, analytics)["answer"]
    assert "1.5 m across" in said                   # 1.0 m at the estimate, 1.5 m measured


def test_reset_goes_back_to_the_estimate(api):
    client, headers, pid = api
    client.post(f"/projects/{pid}/calibrate", json={"a": [0, 0, 0], "b": [2, 0, 0], "real_m": 1.5}, headers=headers)
    r = client.delete(f"/projects/{pid}/calibrate", headers=headers)
    assert r.status_code == 200
    assert r.json()["layout"]["scale_factor"] == 1.0 and r.json()["layout"]["measured"] is None


def test_room_sides_can_set_the_scale_too(api):
    client, headers, pid = api
    r = client.post(f"/projects/{pid}/calibrate", json={"longer_side_m": 5.0}, headers=headers)
    assert r.status_code == 200
    assert r.json()["layout"]["width_m"] == pytest.approx(5.0)
    assert r.json()["layout"]["measured"]["method"] == "room"


def test_an_implausible_measurement_is_refused_and_nothing_is_saved(api):
    client, headers, pid = api
    # 1 unit is 0.5 m at the estimate; claiming it is 40 m is 80 times too big
    r = client.post(f"/projects/{pid}/calibrate", json={"a": [0, 0, 0], "b": [1, 0, 0], "real_m": 40}, headers=headers)
    assert r.status_code == 422 and "too far off" in r.json()["detail"]
    assert client.get(f"/projects/{pid}/analytics", headers=headers).json()["layout"]["measured"] is None


@pytest.mark.parametrize("body", [
    {},                                                                        # nothing
    {"a": [0, 0, 0], "b": [1, 0, 0]},                                          # no distance
    {"a": [0, 0, 0], "b": [1, 0], "real_m": 1},                                # not a 3D point
    {"a": [0, 0, 0], "b": [1, 0, 0], "real_m": -1},
    {"a": [0, 0, 0], "b": [1, 0, 0], "real_m": 1, "longer_side_m": 4},         # both ways at once
    {"shorter_side_m": 3},                                                     # missing the longer side
])
def test_malformed_requests_are_rejected(api, body):
    client, headers, pid = api
    assert client.post(f"/projects/{pid}/calibrate", json=body, headers=headers).status_code == 422


def test_points_on_top_of_each_other_are_refused(api):
    client, headers, pid = api
    r = client.post(f"/projects/{pid}/calibrate", json={"a": [1, 1, 1], "b": [1, 1, 1.01], "real_m": 1}, headers=headers)
    assert r.status_code == 422 and "on top of each other" in r.json()["detail"]


def test_only_the_owner_can_calibrate_or_reset(api):
    client, headers, pid = api
    other = client.post("/auth/signup", json={"email": f"intruder-{uuid.uuid4().hex[:8]}@example.com", "password": "secret123"}).json()["access_token"]
    theirs = {"Authorization": f"Bearer {other}"}
    body = {"a": [0, 0, 0], "b": [2, 0, 0], "real_m": 1.5}
    assert client.post(f"/projects/{pid}/calibrate", json=body, headers=theirs).status_code == 404
    assert client.delete(f"/projects/{pid}/calibrate", headers=theirs).status_code == 404
    assert client.post(f"/projects/{pid}/calibrate", json=body).status_code in (401, 403)


def test_a_scan_without_a_reconstruction_cannot_be_measured(api):
    client, headers, pid = api
    with SessionLocal() as db:
        db.get(Project, pid).detections_json = json.dumps({"detections": [], "meta": {"unit": "view"}})
        db.commit()
    r = client.post(f"/projects/{pid}/calibrate", json={"longer_side_m": 4}, headers=headers)
    assert r.status_code == 409


def test_doors_and_windows_are_structure_not_furniture(api):
    client, headers, pid = api
    analytics = client.get(f"/projects/{pid}/analytics", headers=headers).json()
    assert "door" not in analytics["furniture"] and analytics["structure"] == {"door": 1}
    assert analytics["furniture_total"] == 1
    # a door takes no floor space and does not make a zone of its own
    assert analytics["rooms"]["count"] == 1


def test_the_saved_scale_survives_a_changed_estimate():
    """It is stored as metres per unit, so re-estimating from the same reconstruction cannot corrupt it."""
    entry = scale.from_points(RECON, [0, 0, 0], [2, 0, 0], 1.5)
    assert entry["meters_per_unit"] == pytest.approx(0.75)
    data = scale.save({"meta": {"unit": "m", "reconstruction": dict(RECON, meters_per_unit=0.6)}}, entry)
    assert scale.saved_meters_per_unit(data) == pytest.approx(0.75)
    assert math.isfinite(scale.saved_meters_per_unit({"meta": {"user_scale": {"meters_per_unit": float("nan")}}}) or 0.0)
