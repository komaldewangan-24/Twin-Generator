import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.projects import _get_project_or_404
from app.services import analytics as analytics_service
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