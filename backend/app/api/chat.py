from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.projects import _get_project_or_404
from app.schemas.detection import ChatRequest, ChatResponse
from app.services import analytics as analytics_service
from app.services import chat as chat_service
from app.utils.security import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/{project_id}/ask", response_model=ChatResponse)
def ask(
    project_id: str,
    body: ChatRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = _get_project_or_404(project_id, user_id, db)
    if not project.detections_json:
        raise HTTPException(status_code=404, detail="No detections yet — process a video first")

    analytics = analytics_service.build_analytics(project)
    answer = chat_service.answer(body.question, project, analytics)
    return ChatResponse(question=body.question, answer=answer)