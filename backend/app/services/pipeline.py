"""The processing pipeline, run in the background after a video upload.

  EXTRACTING  frames from the video                       (ffmpeg)
  POSES       camera positions + sparse 3D points         (pycolmap / COLMAP)
  DETECTING   objects, placed in 3D and counted           (YOLO + spatial.py)
  TRAINING_3D photorealistic Gaussian splat for the viewer (Brush)
  DONE

If the camera positions cannot be recovered (blurry, too short, blank walls)
the pipeline keeps going in a reduced mode: objects are still detected, but
counted and placed from the camera view, and no 3D model is built. The reason
is stored so the UI can explain it.
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.project import Project, ProjectStatus
from app.services import detector, extractor, preview, reconstruct, spatial, splat_convert, storage

log = logging.getLogger("uvicorn.error")


def _set_status(project_id: str, status: ProjectStatus, error_message: str | None = None, **updates) -> None:
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return
        project.status = status
        if error_message is not None:
            project.error_message = error_message
        for key, value in updates.items():
            setattr(project, key, value)
        db.commit()


def _update_meta(project_id: str, **values) -> None:
    """Merge keys into detections_json["meta"] (used for notes from later stages)."""
    with SessionLocal() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or not project.detections_json:
            return
        data = json.loads(project.detections_json)
        data.setdefault("meta", {}).update(values)
        project.detections_json = json.dumps(data)
        db.commit()


def write_progress(project_id: str, stage: str, fraction: float, message: str) -> None:
    try:
        Path(storage.progress_path_for(project_id)).write_text(
            json.dumps({"stage": stage, "fraction": round(fraction, 3), "message": message})
        )
    except OSError:
        pass


def read_progress(project_id: str) -> dict | None:
    try:
        return json.loads(Path(storage.progress_path_for(project_id)).read_text())
    except (OSError, ValueError):
        return None


def _detect(frames_dir: str, recon, scene, progress) -> dict:
    """Object detection must never cost the user their 3D model. If the detector
    cannot run (model file missing, ONNX problem...), carry on with an empty
    object list and record why, so the scan still completes."""
    try:
        return detector.run_detection(frames_dir, recon, scene, progress)
    except Exception as exc:  # noqa: BLE001
        log.exception("Object detection failed; continuing without objects")
        return detector.empty_result(scene, str(exc))


def run_pipeline(project_id: str) -> None:
    def progress(stage: str, fraction: float, message: str) -> None:
        write_progress(project_id, stage, fraction, message)

    try:
        frames_dir = storage.frames_dir_for(project_id)

        _set_status(project_id, ProjectStatus.EXTRACTING)
        progress("extract", 0.0, "Extracting frames")
        frame_count = extractor.extract_frames(storage.video_path_for(project_id), frames_dir)
        preview_path = preview.make_contact_sheet(frames_dir, storage.preview_path_for(project_id))

        # ---- camera positions -------------------------------------------------
        _set_status(project_id, ProjectStatus.POSES, frames_dir=frames_dir, frame_count=frame_count, preview_path=preview_path)
        work = Path(storage.work_dir_for(project_id))
        recon = scene = images_dir = None
        recon_error = None
        try:
            frames = reconstruct.select_frames(frames_dir)
            recon, images_dir = reconstruct.estimate_poses(frames, work, progress)
            scene = spatial.build_scene(recon)
        except reconstruct.ReconstructionError as exc:
            recon = scene = None
            recon_error = str(exc)
        except Exception as exc:  # noqa: BLE001 - never lose the whole scan to a 3D problem
            log.exception("Camera pose recovery crashed")
            recon = scene = None
            recon_error = f"The 3D step failed unexpectedly ({exc.__class__.__name__})."

        # ---- objects ----------------------------------------------------------
        _set_status(project_id, ProjectStatus.DETECTING)
        result = _detect(frames_dir, recon, scene, progress)
        result["meta"]["reconstruction_error"] = recon_error
        with SessionLocal() as db:
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project.detections_json = json.dumps(result)
                db.commit()

        # ---- 3D model ---------------------------------------------------------
        if recon is not None:
            _set_status(project_id, ProjectStatus.TRAINING_3D)
            try:
                dataset = reconstruct.prepare_training_set(recon, images_dir, work)
                full = Path(storage.splat_path_for(project_id, ".ply"))
                reconstruct.train_splat(
                    dataset, full, progress,
                    steps=settings.SPLAT_TRAIN_STEPS,
                    max_resolution=settings.SPLAT_MAX_RESOLUTION,
                    max_splats=settings.SPLAT_MAX_SPLATS,
                )
                # The full training file is 100-200 MB; the viewer needs a cleaned, compact copy.
                progress("train", 0.99, "Optimising the 3D model for the browser")
                compact = Path(storage.splat_path_for(project_id, ".splat"))
                stats = splat_convert.ply_to_splat(full, compact)
                full.unlink(missing_ok=True)
                _update_meta(project_id, splat={"splats": stats["out"], "size_mb": stats["mb"]})
                _set_status(project_id, ProjectStatus.TRAINING_3D, splat_path=str(compact))
            except reconstruct.ReconstructionError as exc:
                _update_meta(project_id, splat_error=str(exc))
            except Exception as exc:  # noqa: BLE001
                log.exception("Splat training crashed")
                _update_meta(project_id, splat_error=f"The 3D model step failed unexpectedly ({exc.__class__.__name__}).")
            finally:
                # Keep the small camera files, drop the big duplicates.
                shutil.rmtree(work / "dataset", ignore_errors=True)
                shutil.rmtree(work / "images", ignore_errors=True)
                (work / "database.db").unlink(missing_ok=True)

        _set_status(project_id, ProjectStatus.DONE)
        progress("done", 1.0, "Finished")
    except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
        log.exception("Pipeline failed")
        _set_status(project_id, ProjectStatus.FAILED, error_message=str(exc))
