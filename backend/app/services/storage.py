from app.core.config import settings


def project_dir(project_id: str):
    base = settings.UPLOADS_DIR / project_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def video_path_for(project_id: str) -> str:
    return str(project_dir(project_id) / "video.mp4")


def frames_dir_for(project_id: str) -> str:
    return str(project_dir(project_id) / "frames")


def splat_path_for(project_id: str, ext: str = ".ply") -> str:
    return str(settings.SPLATS_DIR / f"{project_id}{ext}")


def preview_path_for(project_id: str) -> str:
    return str(project_dir(project_id) / "preview.jpg")