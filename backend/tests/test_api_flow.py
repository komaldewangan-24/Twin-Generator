import json
import time

from fastapi.testclient import TestClient

from app.main import app
from tests.video_fixture import generate_test_video

TEST_EMAIL = "flow@test.com"
TEST_PASSWORD = "secret123"


def make_client():
    # Entering the context manager runs the lifespan (create_all) against the
    # isolated temp DB configured in conftest.py.
    return TestClient(app)


def test_full_flow():
    with make_client() as client:
        # 1. signup
        r = client.post("/auth/signup", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. create project
        r = client.post("/projects", json={"name": "Pipeline Test"}, headers=headers)
        assert r.status_code == 201, r.text
        project_id = r.json()["id"]

        # 3. upload synthetic video
        video = generate_test_video("test_flow.mp4", seconds=6)
        with open(video, "rb") as f:
            r = client.post(
                f"/projects/{project_id}/upload",
                files={"file": ("test.mp4", f, "video/mp4")},
                headers=headers,
            )
        assert r.status_code == 201, r.text

        # 4. wait for pipeline
        deadline = time.time() + 120
        status = None
        details = {}
        while time.time() < deadline:
            r = client.get(f"/projects/{project_id}/status", headers=headers)
            details = r.json()
            status = details["status"]
            if status in ("DONE", "FAILED"):
                break
            time.sleep(3)
        assert status == "DONE", f"pipeline failed: {details}"

        # 5. objects endpoint
        r = client.get(f"/projects/{project_id}/objects", headers=headers)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "detections" in data
        assert data["meta"]["frames_processed"] > 0

        # 6. analytics endpoint
        r = client.get(f"/projects/{project_id}/analytics", headers=headers)
        assert r.status_code == 200, r.text
        analytics = r.json()
        assert analytics["furniture_total"] >= 0
        assert "seating_capacity" in analytics

        # calibrated analytics (only valid when at least one object was detected)
        if data["detections"]:
            r = client.get(f"/projects/{project_id}/analytics?room_width_m=4", headers=headers)
            assert r.status_code == 200
            assert r.json()["area"]["calibration"] is not None

        # 7. chat (rule-based fallback, no key configured)
        r = client.post(
            f"/projects/{project_id}/ask",
            json={"question": "How many chairs are present?"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert "chair" in r.json()["answer"].lower()

        # 8. ownership: a second user cannot see the project
        r = client.post("/auth/signup", json={"email": "other@test.com", "password": "secret123"})
        other_token = r.json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}
        r = client.get(f"/projects/{project_id}/status", headers=other_headers)
        assert r.status_code == 404

        # 9. cleanup
        client.delete(f"/projects/{project_id}", headers=headers)
        print(json.dumps({
            "project": project_id,
            "status": status,
            "detections": data["detections"],
            "analytics": analytics,
        }, indent=2, default=str))