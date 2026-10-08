import json

from app.core.database import SessionLocal
from app.models.project import Project, ProjectStatus
from app.services import detector, extractor, preview, storage


def _set_status(project_id: str, status: ProjectStatus, error_message: str | None = None, **updates) -> None:
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        project.status = status
        if error_message is not None:
            project.error_message = error_message
        for key, value in updates.items():
            setattr(project, key, value)
        db.commit()


def run_pipeline(project_id: str) -> None:
    """Processing pipeline: extract frames → preview → detect objects → done."""
    try:
        _set_status(project_id, ProjectStatus.EXTRACTING)
        frame_count = extractor.extract_frames(
            storage.video_path_for(project_id),
            storage.frames_dir_for(project_id),
        )

        preview_path = preview.make_contact_sheet(
            storage.frames_dir_for(project_id),
            storage.preview_path_for(project_id),
        )

        _set_status(
            project_id,
            ProjectStatus.DETECTING,
            frames_dir=storage.frames_dir_for(project_id),
            frame_count=frame_count,
            preview_path=preview_path,
        )

        result = detector.run_detection(storage.frames_dir_for(project_id))
        with SessionLocal() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.detections_json = json.dumps(result)
                db.commit()

        _set_status(project_id, ProjectStatus.DONE)
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        _set_status(project_id, ProjectStatus.FAILED, error_message=str(exc))