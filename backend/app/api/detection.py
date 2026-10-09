import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.projects import _get_project_or_404
from app.schemas.detection import CalibrateRequest
from app.services import analytics as analytics_service
from app.services import scale
from app.utils.security import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/{project_id}/objects")
def get_objects(
    project_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(project_id, user_id, db)
    if not project.detections_json:
        raise HTTPException(status_code=404, detail="No detections yet — processing may be incomplete or failed")
    return json.loads(project.detections_json)


@router.get("/{project_id}/analytics")
def get_analytics(
    project_id: str,
    room_width_m: float | None = None,
    room_height_m: float | None = None,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analytics dashboard. Pass room_width_m to calibrate area to real meters."""
    project = _get_project_or_404(project_id, user_id, db)
    return analytics_service.build_analytics(project, room_width_m=room_width_m, room_height_m=room_height_m)

def _scan_with_reconstruction(project) -> tuple[dict, dict]:
    data = json.loads(project.detections_json) if project.detections_json else {}
    recon = scale.reconstruction(data)
    if not recon:
        raise HTTPException(status_code=409, detail="This scan has no 3D reconstruction, so it cannot be measured.")
    return data, recon


@router.post("/{project_id}/calibrate")
def calibrate(
    project_id: str,
    body: CalibrateRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the real size of the scan from a measurement. Returns the updated analytics."""
    project = _get_project_or_404(project_id, user_id, db)
    data, recon = _scan_with_reconstruction(project)
    try:
        if body.longer_side_m:
            entry = scale.from_room(recon, body.longer_side_m, body.shorter_side_m)
        else:
            entry = scale.from_points(recon, body.a, body.b, body.real_m)
    except scale.ScaleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    project.detections_json = json.dumps(scale.save(data, entry))
    db.commit()
    return analytics_service.build_analytics(project)


@router.delete("/{project_id}/calibrate")
def reset_calibration(
    project_id: str,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Forget the measurement and go back to the estimate."""
    project = _get_project_or_404(project_id, user_id, db)
    data, _ = _scan_with_reconstruction(project)
    project.detections_json = json.dumps(scale.save(data, None))
    db.commit()
    return analytics_service.build_analytics(project)
