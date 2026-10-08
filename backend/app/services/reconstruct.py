"""Video frames -> camera poses -> 3D Gaussian splat.

Stage A (poses): pycolmap (COLMAP's Python package) runs structure-from-motion
on CPU. It recovers where the phone was for every frame and a sparse 3D point
cloud. The same poses feed the object-placement code in `spatial.py`.

Stage B (splat): Brush (Apache-2.0, https://github.com/ArthurBrussee/brush)
trains a Gaussian splat on the GPU. It runs on Apple silicon (Metal), Windows
and Linux, so no NVIDIA card is needed.

Both stages report progress through a callback so the UI can show it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from app.core.config import BASE_DIR

Progress = Callable[[str, float, str], None]  # (stage, fraction 0..1, message)

MAX_SFM_FRAMES = 240
MIN_REGISTERED = 12          # fewer registered frames than this = reconstruction failed
MIN_REGISTERED_RATIO = 0.35  # ...or fewer than this share of the frames we gave it


class ReconstructionError(RuntimeError):
    """A failure with a message that is safe to show to the user."""


# --------------------------------------------------------------------------- frames


def _sharpness(path: Path) -> float:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0.0
    return float(cv2.Laplacian(img, cv2.CV_64F).var())


def select_frames(frames_dir: str | Path, max_frames: int = MAX_SFM_FRAMES) -> list[Path]:
    """Evenly sample the video frames, dropping the blurriest ones first.

    SfM breaks on motion blur, so sharper frames matter more than more frames.
    """
    frames = sorted(Path(frames_dir).glob("*.jpg"))
    if len(frames) <= max_frames:
        scores = [_sharpness(f) for f in frames]
        floor = 0.35 * float(np.median(scores)) if scores else 0.0
        kept = [f for f, s in zip(frames, scores) if s >= floor]
        return kept if len(kept) >= min(len(frames), MIN_REGISTERED * 2) else frames

    # Too many: in each window of consecutive frames keep the sharpest one.
    bins = np.array_split(np.arange(len(frames)), max_frames)
    picked = []
    for idx in bins:
        best = max(idx, key=lambda i: _sharpness(frames[i]))
        picked.append(frames[best])
    return picked


# --------------------------------------------------------------------------- poses


def _quiet_colmap(pycolmap) -> None:
    """COLMAP logs one line per frame to stderr; keep the server log readable."""
    try:
        pycolmap.logging.minloglevel = 2
        pycolmap.logging.alsologtostderr = False
        pycolmap.logging.logtostderr = False
    except AttributeError:
        pass


def estimate_poses(frames: list[Path], work_dir: Path, progress: Progress):
    """Run COLMAP SfM. Returns (pycolmap.Reconstruction, images_dir)."""
    import pycolmap

    _quiet_colmap(pycolmap)
    if len(frames) < MIN_REGISTERED:
        raise ReconstructionError("The video is too short to build a 3D model. Film at least 15 seconds.")

    images_dir = work_dir / "images"
    sparse_dir = work_dir / "sparse"
    db_path = work_dir / "database.db"
    for p in (images_dir, sparse_dir):
        shutil.rmtree(p, ignore_errors=True)
    db_path.unlink(missing_ok=True)
    images_dir.mkdir(parents=True)
    sparse_dir.mkdir(parents=True)

    for f in frames:
        shutil.copy(f, images_dir / f.name)

    progress("poses", 0.02, "Finding features in each frame")
    pycolmap.extract_features(
        str(db_path),
        str(images_dir),
        camera_mode=pycolmap.CameraMode.SINGLE,  # one phone, one lens
    )

    progress("poses", 0.25, "Matching frames to each other")
    if len(frames) <= 260:  # exhaustive finds loop closures; fine up to a few hundred frames
        pycolmap.match_exhaustive(str(db_path))
    else:
        pycolmap.match_sequential(
            str(db_path),
            pairing_options=pycolmap.SequentialPairingOptions(overlap=20, quadratic_overlap=True),
        )

    progress("poses", 0.55, "Solving camera positions")
    recs = pycolmap.incremental_mapping(str(db_path), str(images_dir), str(sparse_dir))
    if not recs:
        raise ReconstructionError(
            "Could not work out the camera path. Film slowly, keep walls and furniture in view, and avoid blank walls."
        )
    best = max(recs.values(), key=lambda r: r.num_reg_images())
    registered = best.num_reg_images()
    if registered < MIN_REGISTERED or registered < MIN_REGISTERED_RATIO * len(frames):
        raise ReconstructionError(
            f"Only {registered} of {len(frames)} frames could be placed in 3D. "
            "Film more slowly with more overlap between views, in good light."
        )
    (sparse_dir / "best").mkdir(exist_ok=True)
    best.write(str(sparse_dir / "best"))
    progress("poses", 1.0, f"Camera path found ({registered} of {len(frames)} frames)")
    return best, images_dir


# --------------------------------------------------------------------------- splat


def find_brush() -> str | None:
    env = os.environ.get("BRUSH_PATH")
    if env and Path(env).exists():
        return env
    for p in sorted((BASE_DIR / "tools").glob("brush-app-*/brush_app*")):
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return shutil.which("brush_app") or shutil.which("brush")


def prepare_training_set(rec, images_dir: Path, work_dir: Path) -> Path:
    """Undistort the images so the splat trainer can treat the camera as an ideal pinhole."""
    import pycolmap

    _quiet_colmap(pycolmap)
    dataset = work_dir / "dataset"
    shutil.rmtree(dataset, ignore_errors=True)
    dataset.mkdir(parents=True)
    pycolmap.undistort_images(str(dataset), str(work_dir / "sparse" / "best"), str(images_dir))
    # Trainers look for sparse/0
    sparse = dataset / "sparse"
    if not (sparse / "0").exists():
        zero = sparse / "0"
        zero.mkdir()
        for f in list(sparse.iterdir()):
            if f.is_file():
                shutil.move(str(f), zero / f.name)
    return dataset


_EXPORT_RE = re.compile(r"export_0*(\d+)\.ply$")


def _latest_export(export_dir: Path) -> tuple[int, Path] | None:
    best = None
    for f in export_dir.glob("export_*.ply"):
        m = _EXPORT_RE.search(f.name)
        if m and (best is None or int(m.group(1)) > best[0]):
            best = (int(m.group(1)), f)
    return best


def train_splat(dataset: Path, out_ply: Path, progress: Progress, steps: int = 12000, max_resolution: int = 1280) -> Path:
    """Train with Brush. Brush writes `export_<iteration>.ply` every few thousand
    steps, which doubles as a progress indicator."""
    brush = find_brush()
    if not brush:
        raise ReconstructionError(
            "The 3D trainer (Brush) is not installed on the server. See the README section 'Real 3D models'."
        )
    export_dir = out_ply.parent / f".{out_ply.stem}_export"
    shutil.rmtree(export_dir, ignore_errors=True)
    export_dir.mkdir(parents=True)

    every = max(1000, steps // 6)
    cmd = [
        brush, str(dataset),
        "--total-steps", str(steps),
        "--max-resolution", str(max_resolution),
        "--export-path", str(export_dir),
        "--export-name", "export_{iter}.ply",
        "--export-every", str(every),
    ]
    progress("train", 0.0, "Training the 3D model")
    log_path = dataset.parent / "brush.log"
    started = time.time()
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        while proc.poll() is None:
            time.sleep(3)
            latest = _latest_export(export_dir)
            if latest:
                frac = min(latest[0] / steps, 0.98)
                progress("train", frac, f"Training the 3D model ({int(frac * 100)}%)")
            if time.time() - started > 60 * 60:
                proc.kill()
                raise ReconstructionError("The 3D model took too long to train and was stopped.")
    if proc.returncode != 0:
        tail = log_path.read_text(errors="ignore")[-300:]
        raise ReconstructionError(f"The 3D trainer failed: {tail.strip()[-200:]}")

    latest = _latest_export(export_dir)
    if not latest:
        raise ReconstructionError("The 3D trainer finished but wrote no model file.")
    out_ply.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(latest[1]), out_ply)
    shutil.rmtree(export_dir, ignore_errors=True)
    progress("train", 1.0, "3D model ready")
    return out_ply
