"""Re-run object detection and room analysis for a scan, without retraining the 3D model.

Use it after upgrading the detector or the analysis code. It reuses the camera
positions saved during processing (storage/uploads/<id>/recon/sparse/best).

    python scripts/reanalyze.py <project-id>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pycolmap  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model)
from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.services import detector, spatial  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    pid = sys.argv[1]
    base = settings.UPLOADS_DIR / pid
    sparse = base / "recon" / "sparse" / "best"
    if not sparse.exists():
        sys.exit(f"No saved camera positions at {sparse}. Process the video again.")

    pycolmap.logging.minloglevel = 2
    rec = pycolmap.Reconstruction(str(sparse))
    scene = spatial.build_scene(rec)
    result = detector.run_detection(str(base / "frames"), rec, scene)

    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == pid).first()
        if not project:
            sys.exit("Project not found.")
        old = json.loads(project.detections_json or "{}").get("meta", {})
        result["meta"]["reconstruction_error"] = None
        for key in ("splat", "splat_error"):
            if key in old:
                result["meta"][key] = old[key]
        project.detections_json = json.dumps(result)
        db.commit()
    print("Updated:", {d["class"]: d["count"] for d in result["detections"]})


if __name__ == "__main__":
    main()
