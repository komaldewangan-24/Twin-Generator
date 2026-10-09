"""Turn a finished scan into the demo scan that ships with the app.

    python scripts/export_demo.py <project-id> ["Name shown on the dashboard"]

Copies the 3D model, 3D structure, preview image and analysis into backend/demo/, then commit
that folder. Anyone who clones the repo can press "Try the demo scan" and see
the full app with no GPU, trainer or video. Use your own scan for the final
submission if you can: the bundled sample comes from a public dataset
(see backend/demo/README.md).
"""

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.main  # noqa: E402,F401  (registers every model)
from app.core.database import SessionLocal  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.services import storage  # noqa: E402
from app.services.demo import DEMO_DATA, DEMO_DIR, DEMO_PREVIEW, DEMO_SPLAT, DEMO_STRUCTURE  # noqa: E402


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    pid = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) == 3 else "Demo scan"
    with SessionLocal() as db:
        p = db.query(Project).filter(Project.id == pid).first()
        if not p or not p.splat_path or not p.detections_json:
            sys.exit("That scan is missing, or has no 3D model / analysis yet.")
        if not str(p.splat_path).endswith(".splat"):
            sys.exit("The scan's model is not a .splat file; process it with the current pipeline first.")
        DEMO_DIR.mkdir(exist_ok=True)
        shutil.copyfile(p.splat_path, DEMO_SPLAT)
        structure = Path(storage.structure_path_for(pid))
        if structure.is_file():
            shutil.copyfile(structure, DEMO_STRUCTURE)
        if p.preview_path and Path(p.preview_path).is_file():
            shutil.copyfile(p.preview_path, DEMO_PREVIEW)
        scan = json.loads(p.detections_json)
        scan.get("meta", {}).pop("user_scale", None)   # a measurement belongs to the person who made it
        DEMO_DATA.write_text(json.dumps({"name": name, "frame_count": p.frame_count, "scan": scan}, separators=(",", ":")))
    mb = DEMO_SPLAT.stat().st_size / 1e6
    print(f"Wrote {DEMO_DIR} ({mb:.1f} MB model). Commit the folder to share it.")


if __name__ == "__main__":
    main()
