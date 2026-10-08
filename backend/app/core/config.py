import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


class Settings:
    APP_NAME: str = "AI Digital Twin Generator"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    # `or` (not a getenv default) so an empty `JWT_SECRET_KEY=` line copied from
    # .env.example can never become an empty signing key.
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY") or "dev-only-secret"
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    # Check Google's current model list; names change. Override in .env if this one is retired.
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
    # Assistant language model (see app/services/llm.py). All optional.
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "")          # gemini | anthropic | ollama | openai
    LLM_MODEL: str = os.getenv("LLM_MODEL", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "")          # for ollama / OpenAI-compatible servers
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")            # app-specific on purpose: never a shell-wide key

    STORAGE_DIR: Path = BASE_DIR / "storage"
    UPLOADS_DIR: Path = STORAGE_DIR / "uploads"
    SPLATS_DIR: Path = STORAGE_DIR / "splats"

    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_MB") or 2048) * 1024 * 1024  # default 2 GB
    ALLOWED_VIDEO_EXTENSIONS: tuple = (".mp4", ".mov", ".webm")
    YOLO_MODEL_PATH: str = "yolov8n.pt"
    # Prefer the larger, more accurate YOLOv8s if exported; fall back to the nano model.
    YOLO_ONNX_PATH: str = os.getenv("YOLO_ONNX_PATH") or str(
        next((p for p in (BASE_DIR / "models" / "yolov8s.onnx", BASE_DIR / "models" / "yolov8n.onnx") if p.exists()), BASE_DIR / "models" / "yolov8n.onnx")
    )

    # Splat training length. More steps = sharper model but longer wait (about 16 min for
    # 12000 on an Apple M4). 7000 is a decent quick preset.
    SPLAT_TRAIN_STEPS: int = int(os.getenv("SPLAT_TRAIN_STEPS") or 12000)

    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24


settings = Settings()

settings.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
settings.SPLATS_DIR.mkdir(parents=True, exist_ok=True)
