"""Measure how accurate a scan is against what you measured by hand.

1. Scan a room with the app. Note the project id (it's in the page URL).
2. Measure the room with a tape and count the objects yourself. Write truth.json:

   {
     "room": {"longer_side_m": 5.4, "shorter_side_m": 3.9, "ceiling_m": 2.6},
     "counts": {"chair": 6, "dining table": 2, "couch": 1}
   }

3. Run:  python scripts/evaluate.py <project-id> truth.json

It prints a Markdown report (paste it into your project report): the app's
unaided estimates versus your measurements, then the same room after you give
the app the longer side, which is what a user would do to correct the scale.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.services.analytics import build_analytics  # noqa: E402


def pct(est: float, truth: float) -> str:
    return f"{100 * (est - truth) / truth:+.0f}%" if truth else "n/a"


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    project_id, truth_path = sys.argv[1], sys.argv[2]
    truth = json.loads(Path(truth_path).read_text())

    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.detections_json:
            sys.exit("Project not found or not processed yet.")
        raw = build_analytics(project)
        longer = truth.get("room", {}).get("longer_side_m")
        calibrated = build_analytics(project, room_width_m=longer) if longer else None

    lay = raw.get("layout")
    print(f"# Accuracy report: {project.name}\n")

    print("## Object counts\n")
    print("| Object | Counted by hand | App | Error |\n|---|---|---|---|")
    errors = []
    for cls, actual in truth.get("counts", {}).items():
        est = raw["furniture"].get(cls, 0)
        errors.append(abs(est - actual))
        print(f"| {cls} | {actual} | {est} | {est - actual:+d} |")
    if errors:
        print(f"\nMean absolute error: **{sum(errors) / len(errors):.2f}** objects per kind.\n")

    if lay:
        room = truth.get("room", {})
        print("## Room size (no help from the user)\n")
        print("| Measure | Tape measure | App estimate | Error |\n|---|---|---|---|")
        for key, label, est in (
            ("longer_side_m", "Longer side (m)", lay["width_m"]),
            ("shorter_side_m", "Shorter side (m)", lay["depth_m"]),
            ("ceiling_m", "Ceiling (m)", lay["ceiling_height_m"]),
        ):
            if key in room:
                print(f"| {label} | {room[key]} | {est} | {pct(est, room[key])} |")
        if "longer_side_m" in room and "shorter_side_m" in room:
            actual_area = room["longer_side_m"] * room["shorter_side_m"]
            print(f"| Floor area (m²) | {actual_area:.1f} | {lay['area_m2']} | {pct(lay['area_m2'], actual_area)} |")
        print(f"\nScale method: {raw['area']['calibration']['method']}.\n")

        if calibrated:
            cl = calibrated["layout"]
            print(f"## After the user enters the longer side ({longer} m)\n")
            print("| Measure | Tape measure | App | Error |\n|---|---|---|---|")
            if "shorter_side_m" in room:
                print(f"| Shorter side (m) | {room['shorter_side_m']} | {cl['depth_m']} | {pct(cl['depth_m'], room['shorter_side_m'])} |")
            if "ceiling_m" in room:
                print(f"| Ceiling (m) | {room['ceiling_m']} | {cl['ceiling_height_m']} | {pct(cl['ceiling_height_m'], room['ceiling_m'])} |")
            print()
    else:
        print("No 3D reconstruction for this scan, so room size was not estimated.")


if __name__ == "__main__":
    main()
