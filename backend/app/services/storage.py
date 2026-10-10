from app.core.config import settings


def project_dir(project_id: str):
    base = settings.UPLOADS_DIR / project_id
    base.mkdir(parents=True, exist_ok=True)
    return base


def video_path_for(project_id: str) -> str:
    return str(project_dir(project_id) / "video.mp4")


def photos_dir_for(project_id: str) -> str:
    """The photos a scan was made from, when it was made from photos instead of a video."""
    return str(settings.UPLOADS_DIR / project_id / "photos")


def frames_dir_for(project_id: str) -> str:
    return str(project_dir(project_id) / "frames")


def splat_path_for(project_id: str, ext: str = ".ply") -> str:
    return str(settings.SPLATS_DIR / f"{project_id}{ext}")


def preview_path_for(project_id: str) -> str:
    return str(project_dir(project_id) / "preview.jpg")

def work_dir_for(project_id: str) -> str:
    """Scratch space for SfM and splat training (deleted with the project)."""
    d = project_dir(project_id) / "recon"
    d.mkdir(parents=True, exist_ok=True)
    return str(d)


def progress_path_for(project_id: str) -> str:
    return str(project_dir(project_id) / "progress.json")


def structure_path_for(project_id: str) -> str:
    """The 3D point cloud recovered from the video (see services/structure.py)."""
    return str(project_dir(project_id) / "structure.points")
