"""Authenticated file serving.

Browsers cannot attach an Authorization header to <img src> or to the 3D
viewer's download, so the client first asks for a short-lived "file token"
(this requires the normal login), then puts it in the URL. A token is only valid
for files the user owns, and it expires after 30 minutes.
"""

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.project import Project
from app.utils.security import get_current_user

router = APIRouter(tags=["files"])

FILE_TOKEN_MINUTES = 30
SPLAT_SUFFIXES = {".ply", ".splat", ".spz"}


@router.post("/files/token")
def create_file_token(user_id: str = Depends(get_current_user)):
    exp = datetime.utcnow() + timedelta(minutes=FILE_TOKEN_MINUTES)
    token = jwt.encode(
        {"sub": user_id, "scope": "files", "exp": exp},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"token": token, "expires_in": FILE_TOKEN_MINUTES * 60}


def _user_from_file_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="This link has expired. Reload the page.")
    if payload.get("scope") != "files" or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid file link")
    return payload["sub"]


@router.get("/files/{project_id}/{name}")
def get_file(project_id: str, name: str, t: str = Query(...), db: Session = Depends(get_db)):
    """`name` is `preview.jpg`, `structure.points` or `model.<ext>`; the extension also tells the
    3D viewer which file format to expect."""
    user_id = _user_from_file_token(t)
    project = db.query(Project).filter(Project.id == project_id, Project.user_id == user_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Not found")

    if name == "preview.jpg" and project.preview_path:
        path, media = Path(project.preview_path), "image/jpeg"
    elif name == "structure.points":
        path, media = settings.UPLOADS_DIR / project.id / "structure.points", "application/octet-stream"
    elif name.startswith("model.") and project.splat_path and Path(name).suffix in SPLAT_SUFFIXES:
        path, media = Path(project.splat_path), "application/octet-stream"
        if path.suffix != Path(name).suffix:
            raise HTTPException(status_code=404, detail="Not found")
    else:
        raise HTTPException(status_code=404, detail="Not found")

    if not path.is_file():
        raise HTTPException(status_code=404, detail="File is missing on the server")
    return FileResponse(path, media_type=media, headers={"Cache-Control": "private, max-age=600"})
