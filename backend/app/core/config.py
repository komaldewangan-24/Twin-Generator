import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


class Settings:
    APP_NAME: str = "AI Digital Twin Generator"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-only-secret")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    SPLATS_DIR: Path = STORAGE_DIR / "splats"

    MAX_UPLOAD_BYTES: int = 500 * 1024 * 1024  # 500 MB
    ALLOWED_VIDEO_EXTENSIONS: tuple = (".mp4", ".mov", ".webm")
    YOLO_MODEL_PATH: str = "yolov8n.pt"
    YOLO_ONNX_PATH: str = str(BASE_DIR / "models" / "yolov8n.onnx")

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24


settings = Settings()

settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.SPLATS_DIR.mkdir(parents=True, exist_ok=True)
