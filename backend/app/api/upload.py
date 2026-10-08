import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.project import PROCESSING_STATUSES, Project, ProjectStatus
from app.api.projects import _get_project_or_404
from app.schemas.project import ProjectResponse
from app.services import storage
from app.services.pipeline import read_progress, run_pipeline
from app.utils.security import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])

STAGE_ORDER = ["UPLOADED", "EXTRACTING", "POSES", "DETECTING", "TRAINING_3D", "DONE"]


def _save_file(file: UploadFile, dest: str) -> int:
    """Stream file to disk in chunks (safe for large videos). Returns bytes written.

    Writes to a temp file first and only replaces `dest` once the whole file is
    in, so a rejected or interrupted upload never destroys the previous one.
    """
    tmp = f"{dest}.part"
    written = 0
    try:
        with open(tmp, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"File exceeds the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit")
                out.write(chunk)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return written


@router.post("/{project_id}/upload", status_code=201)
def upload_video(
    project_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(project_id, user_id, db)
    if project.status in PROCESSING_STATUSES:
        raise HTTPException(status_code=409, detail="This scan is still processing. Wait for it to finish.")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported type {ext}. Use .mp4/.mov/.webm")

    dest = storage.video_path_for(project_id)
    _save_file(file, dest)

    project.status = ProjectStatus.UPLOADED
    project.video_path = dest
    project.error_message = None
    project.detections_json = None
    project.splat_path = None
    db.commit()
    db.refresh(project)

    background.add_task(run_pipeline, project_id)
    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/splat", status_code=201)
def upload_splat(
    project_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach a pre-trained gaussian splat (.ply/.splat) produced by the
    external training stage (Colab / Luma export)."""
    project = _get_project_or_404(project_id, user_id, db)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in (".ply", ".splat", ".spz"):
        raise HTTPException(status_code=400, detail="Use .ply, .splat or .spz splat files")

    dest = storage.splat_path_for(project_id, ext)
    _save_file(file, dest)

    project.splat_path = dest
    project.status = ProjectStatus.DONE  # viewer-ready
    project.error_message = None
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.post("/{project_id}/splat/demo", status_code=201)
def attach_demo_splat(
    project_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Attach the bundled demo gaussian splat so the 3D viewer works
    immediately without an external training run."""
    project = _get_project_or_404(project_id, user_id, db)
    demo = Path(settings.SPLATS_DIR) / "demo.splat"
    if not demo.exists():
        raise HTTPException(status_code=404, detail="Demo model missing on server")
    project.splat_path = str(demo)
    project.status = ProjectStatus.DONE
    project.error_message = None
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/status")
def get_status(
    project_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(project_id, user_id, db)

    status_value = project.status.value
    if status_value not in STAGE_ORDER:
        stages = [{"key": key, "done": False} for key in STAGE_ORDER]
    else:
        stages = []
        for key in STAGE_ORDER:
            done = STAGE_ORDER.index(key) < STAGE_ORDER.index(status_value) or key == status_value
            stages.append({"key": key, "done": done})
    return {
        "status": project.status.value,
        "error_message": project.error_message,
        "frame_count": project.frame_count,
        "progress": read_progress(project_id) if project.status in PROCESSING_STATUSES else None,
        "has_detections": bool(project.detections_json),
        "splat_ready": bool(project.splat_path),
        "has_video": bool(project.video_path),
        "stages": stages,
    }