import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer as SQLAlchemyInteger, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProjectStatus(str, enum.Enum):
    CREATED = "CREATED"
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    POSES = "POSES"
    DETECTING = "DETECTING"
    TRAINING_3D = "TRAINING_3D"
    DONE = "DONE"
    FAILED = "FAILED"


# Statuses during which a background job is working on the project.
PROCESSING_STATUSES = (
    ProjectStatus.UPLOADED,
    ProjectStatus.EXTRACTING,
    ProjectStatus.POSES,
    ProjectStatus.DETECTING,
    ProjectStatus.TRAINING_3D,
)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.CREATED, nullable=False)
    error_message = Column(Text, nullable=True)
    scan_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    video_path = Column(String(500), nullable=True)
    frames_dir = Column(String(500), nullable=True)
    frame_count = Column(SQLAlchemyInteger, nullable=True)
    splat_path = Column(String(500), nullable=True)
    preview_path = Column(String(500), nullable=True)
    detections_json = Column(Text, nullable=True)

    user = relationship("User", back_populates="projects")

    # Flags for the API: clients never see server file paths.
    @property
    def has_video(self) -> bool:
        return bool(self.video_path)

    @property
    def has_preview(self) -> bool:
        return bool(self.preview_path)

    @property
    def has_structure(self) -> bool:
        from app.core.config import settings

        return (settings.UPLOADS_DIR / self.id / "structure.points").is_file()

    @property
    def has_splat(self) -> bool:
        return bool(self.splat_path)

    @property
    def splat_ext(self) -> str | None:
        return "." + self.splat_path.rsplit(".", 1)[-1].lower() if self.splat_path and "." in self.splat_path else None
