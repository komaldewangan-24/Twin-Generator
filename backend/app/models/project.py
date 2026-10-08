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
    TRAINING_3D = "TRAINING_3D"
    DETECTING = "DETECTING"
    DONE = "DONE"
    FAILED = "FAILED"


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
