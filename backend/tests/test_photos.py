"""A scan built from photos instead of a video."""

import io
import uuid
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.project import Project, ProjectStatus
from app.services import photos, pipeline, reconstruct, storage


def _picture(size=(400, 300), seed=0) -> Image.Image:
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8))


def _jpeg_bytes(size=(400, 300), seed=0, orientation: int | None = None) -> bytes:
    buf = io.BytesIO()
    img = _picture(size, seed)
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation                       # the "rotate me" flag a phone writes
        img.save(buf, "JPEG", exif=exif)
    else:
        img.save(buf, "JPEG")
    return buf.getvalue()


def _write_set(folder: Path, n: int, size=(400, 300)) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(1, n + 1):
        (folder / f"IMG_{i}.jpg").write_bytes(_jpeg_bytes(size, seed=i))


# ---------------------------------------------------------------------------- preparing photos


def test_photos_become_frames_scaled_by_their_short_side(tmp_path):
    _write_set(tmp_path / "in", 16, size=(1600, 1200))              # a landscape camera photo
    count = photos.prepare_photos(tmp_path / "in", tmp_path / "frames")
    assert count == 16
    first = Image.open(tmp_path / "frames" / "frame_00001.jpg")
    assert first.size == (960, 720)                                  # short side 720, shape kept
    assert sorted(p.name for p in (tmp_path / "frames").glob("*.jpg"))[-1] == "frame_00016.jpg"


def test_a_phones_rotation_flag_is_applied(tmp_path):
    """A portrait phone photo is stored as landscape pixels plus a flag; without applying it every portrait
    photo would be sideways and could not be linked to the others."""
    folder = tmp_path / "in"
    _write_set(folder, 15)
    (folder / "IMG_1.jpg").write_bytes(_jpeg_bytes((400, 300), orientation=6))      # 400x300 pixels, rotate 90 degrees
    photos.prepare_photos(folder, tmp_path / "frames")
    assert Image.open(tmp_path / "frames" / "frame_00001.jpg").size == (720, 960)    # portrait now


def test_photos_are_taken_in_the_order_of_their_names(tmp_path):
    """IMG_2 comes before IMG_10: consecutive photos overlap, so the order matters to the linking."""
    folder = tmp_path / "in"
    folder.mkdir()
    for i, shade in zip((1, 2, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22), range(15)):
        Image.new("RGB", (300, 300), (shade * 15, 0, 0)).save(folder / f"IMG_{i}.jpg", quality=100)
    photos.prepare_photos(folder, tmp_path / "frames")
    reds = [np.array(Image.open(tmp_path / "frames" / f"frame_{n:05d}.jpg"))[:, :, 0].mean() for n in range(1, 16)]
    assert reds == sorted(reds), "the 15 photos must keep the order IMG_1, IMG_2, IMG_10, ..."


def test_an_unreadable_photo_is_skipped_but_too_few_is_explained(tmp_path):
    folder = tmp_path / "in"
    _write_set(folder, 15)
    (folder / "IMG_99.jpg").write_bytes(b"not a picture at all")
    assert photos.prepare_photos(folder, tmp_path / "frames") == 15       # the broken one is skipped

    (folder / "IMG_15.jpg").unlink()
    with pytest.raises(RuntimeError, match=r"Only 14 usable photos.*at least 15.*IMG_99"):
        photos.prepare_photos(folder, tmp_path / "frames2")


@pytest.mark.skipif(not photos.HEIC_SUPPORTED, reason="pillow-heif is not installed")
def test_iphone_heic_photos_are_read(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    for i in range(15):
        _picture((640, 480), seed=i).save(folder / f"IMG_{i:04d}.heic")
    assert photos.prepare_photos(folder, tmp_path / "frames") == 15


def test_photos_of_mixed_shapes_get_a_camera_each(tmp_path):
    """One shared camera cannot describe portrait and landscape photos together."""
    a, b = tmp_path / "a", tmp_path / "b"
    _write_set(a, 15, size=(400, 300))
    _write_set(b, 15, size=(400, 300))
    (b / "IMG_3.jpg").write_bytes(_jpeg_bytes((300, 400)))
    photos.prepare_photos(a, tmp_path / "fa")
    photos.prepare_photos(b, tmp_path / "fb")
    assert reconstruct.same_size(sorted((tmp_path / "fa").glob("*.jpg"))) is True
    assert reconstruct.same_size(sorted((tmp_path / "fb").glob("*.jpg"))) is False


# ---------------------------------------------------------------------------- the API


@pytest.fixture()
def api(monkeypatch):
    started = []
    monkeypatch.setattr("app.api.upload.run_pipeline", lambda pid: started.append(pid))    # the pipeline has its own test
    with TestClient(app) as client:
        token = client.post("/auth/signup", json={"email": f"photos-{uuid.uuid4().hex[:8]}@example.com", "password": "secret123"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        pid = client.post("/projects", json={"name": "Photo room"}, headers=headers).json()["id"]
        yield client, headers, pid, started


def _files(n, name="IMG_{i}.jpg", content=None):
    return [("files", (name.format(i=i), content or _jpeg_bytes(seed=i), "image/jpeg")) for i in range(1, n + 1)]


def test_photos_are_uploaded_and_processing_starts(api):
    client, headers, pid, started = api
    r = client.post(f"/projects/{pid}/photos", files=_files(16), headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "UPLOADED" and body["has_photos"] is True and body["has_video"] is False
    assert started == [pid]
    assert len(list(Path(storage.photos_dir_for(pid)).iterdir())) == 16


def test_too_few_or_unsupported_photos_are_refused_clearly(api):
    client, headers, pid, started = api
    few = client.post(f"/projects/{pid}/photos", files=_files(5), headers=headers)
    assert few.status_code == 400 and "at least 15" in few.json()["detail"]
    pdf = client.post(f"/projects/{pid}/photos", files=_files(15) + [("files", ("plan.pdf", b"%PDF", "application/pdf"))], headers=headers)
    assert pdf.status_code == 400 and "plan.pdf" in pdf.json()["detail"]
    assert started == [] and not Path(storage.photos_dir_for(pid)).exists()


def test_a_hostile_file_name_cannot_leave_the_folder(api):
    client, headers, pid, _ = api
    files = _files(14) + [("files", ("../../../evil.jpg", _jpeg_bytes(seed=99), "image/jpeg"))]
    assert client.post(f"/projects/{pid}/photos", files=files, headers=headers).status_code == 201
    names = sorted(p.name for p in Path(storage.photos_dir_for(pid)).iterdir())
    assert len(names) == 15 and all("/" not in n and not n.startswith(".") for n in names)
    assert not (settings.UPLOADS_DIR.parent / "evil.jpg").exists() and not (settings.UPLOADS_DIR / "evil.jpg").exists()


def test_only_the_owner_can_upload_photos_and_not_while_processing(api):
    client, headers, pid, started = api
    other = client.post("/auth/signup", json={"email": f"other-{uuid.uuid4().hex[:8]}@example.com", "password": "secret123"}).json()["access_token"]
    assert client.post(f"/projects/{pid}/photos", files=_files(15), headers={"Authorization": f"Bearer {other}"}).status_code == 404
    assert client.post(f"/projects/{pid}/photos", files=_files(15)).status_code in (401, 403)
    with SessionLocal() as db:
        db.get(Project, pid).status = ProjectStatus.POSES
        db.commit()
    assert client.post(f"/projects/{pid}/photos", files=_files(15), headers=headers).status_code == 409
    assert started == []


def test_a_scan_comes_from_one_source_the_latest_upload_wins(api):
    client, headers, pid, _ = api
    assert client.post(f"/projects/{pid}/photos", files=_files(15), headers=headers).status_code == 201
    assert client.get(f"/projects/{pid}", headers=headers).json()["has_photos"] is True
    with SessionLocal() as db:
        db.get(Project, pid).status = ProjectStatus.DONE
        db.commit()
    from tests.video_fixture import generate_test_video

    with open(generate_test_video("photos_replace.mp4", seconds=2), "rb") as f:
        assert client.post(f"/projects/{pid}/upload", files={"file": ("v.mp4", f, "video/mp4")}, headers=headers).status_code == 201
    after = client.get(f"/projects/{pid}", headers=headers).json()
    assert after["has_video"] is True and after["has_photos"] is False
    with SessionLocal() as db:
        db.get(Project, pid).status = ProjectStatus.DONE
        db.commit()
    assert client.post(f"/projects/{pid}/photos", files=_files(15), headers=headers).status_code == 201
    final = client.get(f"/projects/{pid}", headers=headers).json()
    assert final["has_photos"] is True and final["has_video"] is False


# ---------------------------------------------------------------------------- the pipeline


def test_the_pipeline_builds_a_scan_from_photos_without_a_video(tmp_path, monkeypatch):
    monkeypatch.setattr(reconstruct, "find_brush", lambda: None)       # no training here
    with TestClient(app) as client:                                    # creates the tables in the test database
        token = client.post("/auth/signup", json={"email": f"pipe-{uuid.uuid4().hex[:8]}@example.com", "password": "secret123"}).json()["access_token"]
        pid = client.post("/projects", json={"name": "From photos"}, headers={"Authorization": f"Bearer {token}"}).json()["id"]
    _write_set(Path(storage.photos_dir_for(pid)), 18, size=(800, 600))
    with SessionLocal() as db:
        db.get(Project, pid).status = ProjectStatus.UPLOADED
        db.commit()

    pipeline.run_pipeline(pid)

    with SessionLocal() as db:
        project = db.get(Project, pid)
        assert project.status == ProjectStatus.DONE, project.error_message
        assert project.frame_count == 18 and project.video_path is None
        assert Path(project.preview_path).is_file()
    assert len(list(Path(storage.frames_dir_for(pid)).glob("*.jpg"))) == 18


def test_too_few_usable_photos_fail_the_scan_with_the_reason(tmp_path):
    with TestClient(app) as client:
        token = client.post("/auth/signup", json={"email": f"few-{uuid.uuid4().hex[:8]}@example.com", "password": "secret123"}).json()["access_token"]
        pid = client.post("/projects", json={"name": "Broken photos"}, headers={"Authorization": f"Bearer {token}"}).json()["id"]
    folder = Path(storage.photos_dir_for(pid))
    _write_set(folder, 15)
    for i in range(1, 6):
        (folder / f"IMG_{i}.jpg").write_bytes(b"corrupt")
    with SessionLocal() as db:
        db.get(Project, pid).status = ProjectStatus.UPLOADED
        db.commit()
    pipeline.run_pipeline(pid)
    with SessionLocal() as db:
        project = db.get(Project, pid)
        assert project.status == ProjectStatus.FAILED
        assert "Only 10 usable photos" in project.error_message and "at least 15" in project.error_message
