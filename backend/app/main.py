from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import settings
from app.core.database import Base, engine

from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.upload import router as upload_router
from app.api.detection import router as detection_router
from app.api.chat import router as chat_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create tables on startup (dev convenience — use Alembic for prod)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc):
    """Return JSON for unhandled errors.

    Without this, Starlette's ServerErrorMiddleware re-raises and the browser
    reports a misleading CORS failure (because the error response bypasses
    CORSMiddleware). Returning a proper JSONResponse keeps the real message.
    """
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static media: trained splats and generated previews
app.mount("/splats", StaticFiles(directory=settings.SPLATS_DIR), name="splats")
app.mount("/media", StaticFiles(directory=settings.UPLOADS_DIR), name="media")


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/health/db")
def health_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(upload_router)
app.include_router(detection_router)
app.include_router(chat_router)