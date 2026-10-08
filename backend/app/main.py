import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.models.project import PROCESSING_STATUSES, Project, ProjectStatus

from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.upload import router as upload_router
from app.api.detection import router as detection_router
from app.api.chat import router as chat_router
from app.api.files import router as files_router

logger = logging.getLogger("uvicorn.error")


def _fail_interrupted_projects() -> None:
    """A server restart kills background jobs; don't leave projects spinning forever."""
    with SessionLocal() as db:
        stuck = db.query(Project).filter(Project.status.in_(PROCESSING_STATUSES))
        for project in stuck:
            project.status = ProjectStatus.FAILED
            project.error_message = "Processing was interrupted by a server restart. Upload the video again."
        db.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Create tables on startup (dev convenience — use Alembic for prod)
    Base.metadata.create_all(engine)
    _fail_interrupted_projects()
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(_request, exc):
    """Return JSON for unhandled errors.

    Without this, Starlette's ServerErrorMiddleware re-raises and the browser
    reports a misleading CORS failure (because the error response bypasses
    CORSMiddleware). The real error goes to the server log, not to the client.
    """
    logger.exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

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
app.include_router(files_router)