"""Train the photoreal 3D model of an existing scan again, with the current settings and converter.

    python scripts/retrain.py <project-id>

Use it after upgrading the trainer settings or the splat converter: scans processed earlier keep
the model they were given, because the full training file is deleted once it has been converted.
It reuses the camera positions and frames saved with the scan, so it does not repeat the camera
step or the object detection, and the objects and floor plan stay exactly as they are. It needs the
Brush trainer (python scripts/install_brush.py) and takes as long as the 3D step of a new scan.
"""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pycolmap  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model)
from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.services import pipeline, reconstruct, splat_convert, storage  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    pid = sys.argv[1]
    base = settings.UPLOADS_DIR / pid
    sparse = base / "recon" / "sparse" / "best"
    frames = base / "frames"
    if not sparse.exists() or not frames.exists():
        sys.exit(f"No saved camera positions or frames for {pid}. Process the video again.")
    with SessionLocal() as db:
        if not db.query(Project).filter(Project.id == pid).first():
            sys.exit("Project not found.")

    def progress(stage: str, fraction: float, message: str) -> None:
        print(f"\r  {stage} {fraction * 100:5.1f}%  {message[:70]:70s}", end="", flush=True)

    pycolmap.logging.minloglevel = 2
    rec = pycolmap.Reconstruction(str(sparse))
    work = Path(tempfile.mkdtemp(prefix="twin_retrain_"))
    try:
        (work / "sparse").mkdir()
        shutil.copytree(sparse, work / "sparse" / "best")
        dataset = reconstruct.prepare_training_set(rec, frames, work)
        full = Path(storage.splat_path_for(pid, ".ply"))
        reconstruct.train_splat(
            dataset, full, progress,
            steps=settings.SPLAT_TRAIN_STEPS,
            max_resolution=settings.SPLAT_MAX_RESOLUTION,
            max_splats=settings.SPLAT_MAX_SPLATS,
        )
        print()
        compact = Path(storage.splat_path_for(pid, ".splat"))
        stats = splat_convert.ply_to_splat(full, compact)
        full.unlink(missing_ok=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    pipeline._update_meta(pid, splat={"splats": stats["out"], "size_mb": stats["mb"]}, splat_error=None)
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == pid).first()
        project.splat_path = str(compact)
        db.commit()
    print(f"Done: {stats['out']:,} splats, {stats['mb']} MB -> {compact}")


if __name__ == "__main__":
    main()
