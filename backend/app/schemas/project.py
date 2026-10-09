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
    frame_count: int | None = None
    has_video: bool = False
    has_preview: bool = False
    has_splat: bool = False
    has_structure: bool = False
    splat_ext: str | None = None

    model_config = {"from_attributes": True}
