"""A ready-made demo scan that ships inside the repository.

Training a 3D model needs a GPU, a downloaded trainer and 10+ minutes. A demo
scan lets anyone see the full app (3D model, objects, floor plan, assistant)
the moment it starts, which is what you need for a presentation or on a laptop
that cannot train. Make or refresh it from any finished scan with
`python scripts/export_demo.py <project-id>`.

Files in backend/demo/: demo.splat (the 3D model), structure.points (the 3D point cloud),
preview.jpg, demo.json.
"""

from __future__ import annotations

import json
import shutil

from sqlalchemy.orm import Session

from app.core.config import BASE_DIR
from app.models.project import Project, ProjectStatus
from app.services import storage

DEMO_DIR = BASE_DIR / "demo"
DEMO_SPLAT = DEMO_DIR / "demo.splat"
DEMO_PREVIEW = DEMO_DIR / "preview.jpg"
DEMO_DATA = DEMO_DIR / "demo.json"
DEMO_STRUCTURE = DEMO_DIR / "structure.points"


def available() -> bool:
    return DEMO_SPLAT.is_file() and DEMO_DATA.is_file()


def create_demo_project(db: Session, user_id: str) -> tuple[Project, bool]:
    """Returns (project, created). A user gets one demo scan, not a copy per click."""
    data = json.loads(DEMO_DATA.read_text())
    existing = db.query(Project).filter(Project.user_id == user_id, Project.name == data["name"]).first()
    if existing:
        return existing, False

    project = Project(
        user_id=user_id,
        name=data["name"],
        status=ProjectStatus.DONE,
        frame_count=data.get("frame_count"),
        detections_json=json.dumps(data["scan"]),
    )
    db.add(project)
    db.flush()  # assigns the id used for the file names

    splat = storage.splat_path_for(project.id, ".splat")
    shutil.copyfile(DEMO_SPLAT, splat)
    project.splat_path = splat
    if DEMO_STRUCTURE.is_file():
        shutil.copyfile(DEMO_STRUCTURE, storage.structure_path_for(project.id))
    if DEMO_PREVIEW.is_file():
        preview = storage.preview_path_for(project.id)
        shutil.copyfile(DEMO_PREVIEW, preview)
        project.preview_path = preview
    db.commit()
    db.refresh(project)
    return project, True
