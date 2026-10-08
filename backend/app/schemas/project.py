from datetime import datetime

from pydantic import BaseModel

from app.models.project import ProjectStatus


class ProjectCreate(BaseModel):
    name: str


class ProjectUpdate(BaseModel):
    name: str | None = None


class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    status: ProjectStatus
    error_message: str | None = None
    scan_date: datetime
    video_path: str | None = None
    frame_count: int | None = None
    splat_path: str | None = None
    preview_path: str | None = None

    model_config = {"from_attributes": True}
