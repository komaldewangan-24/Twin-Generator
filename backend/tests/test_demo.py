"""The bundled demo scan: one click gives any user the full app, with no GPU or video."""

from fastapi.testclient import TestClient

from app.main import app


def make_client():
    return TestClient(app)


def test_demo_scan_is_added_once_and_served_privately(tmp_path, monkeypatch):
    """The demo scan lets anyone see the full app with no GPU, trainer or video."""
    import json as _json

    from app.services import demo

    (tmp_path / "demo.splat").write_bytes(b"\x00" * 64)
    (tmp_path / "preview.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    (tmp_path / "demo.json").write_text(_json.dumps({
        "name": "Demo: Test room", "frame_count": 10,
        "scan": {"calibration": None, "detections": [], "meta": {"unit": "m"}},
    }))
    monkeypatch.setattr(demo, "DEMO_SPLAT", tmp_path / "demo.splat")
    monkeypatch.setattr(demo, "DEMO_PREVIEW", tmp_path / "preview.jpg")
    monkeypatch.setattr(demo, "DEMO_DATA", tmp_path / "demo.json")
    (tmp_path / "structure.points").write_bytes(b"TWSP" + (0).to_bytes(4, "little"))
    monkeypatch.setattr(demo, "DEMO_STRUCTURE", tmp_path / "structure.points")

    with make_client() as client:
        a = client.post("/auth/signup", json={"email": "demo-a@example.com", "password": "secret123"}).json()["access_token"]
        b = client.post("/auth/signup", json={"email": "demo-b@example.com", "password": "secret123"}).json()["access_token"]
        ha, hb = {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {b}"}

        first = client.post("/projects/demo", headers=ha)
        assert first.status_code == 201
        project = first.json()
        assert project["status"] == "DONE" and project["has_splat"] and project["splat_ext"] == ".splat"

        again = client.post("/projects/demo", headers=ha)           # pressing the button twice must not duplicate
        assert again.status_code == 200 and again.json()["id"] == project["id"]
        assert len([p for p in client.get("/projects", headers=ha).json() if p["name"] == "Demo: Test room"]) == 1

        token = client.post("/files/token", headers=ha).json()["token"]
        got = client.get(f"/files/{project['id']}/model.splat", params={"t": token})
        assert got.status_code == 200 and len(got.content) == 64
        other = client.post("/files/token", headers=hb).json()["token"]
        assert client.get(f"/files/{project['id']}/model.splat", params={"t": other}).status_code == 404

        assert project["has_structure"] is True
        structure = client.get(f"/files/{project['id']}/structure.points", params={"t": token})
        assert structure.status_code == 200 and structure.content[:4] == b"TWSP"
        assert client.get(f"/files/{project['id']}/structure.points", params={"t": other}).status_code == 404
        assert client.get(f"/projects/{project['id']}/objects", headers=ha).status_code == 200
        assert client.delete(f"/projects/{project['id']}", headers=ha).status_code == 204
        assert demo.DEMO_SPLAT.exists(), "deleting a user's copy must never delete the bundled demo"


def test_demo_scan_reports_clearly_when_it_is_not_bundled(tmp_path, monkeypatch):
    from app.services import demo

    monkeypatch.setattr(demo, "DEMO_SPLAT", tmp_path / "missing.splat")
    monkeypatch.setattr(demo, "DEMO_DATA", tmp_path / "missing.json")
    with make_client() as client:
        token = client.post("/auth/signup", json={"email": "demo-c@example.com", "password": "secret123"}).json()["access_token"]
        r = client.post("/projects/demo", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 404 and "not included" in r.json()["detail"]
