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

GROWTH_STOP_FRACTION = 0.55
TRAIN_TIMEOUT_MIN = 150      # a slow laptop GPU needs well over an hour for the high preset
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


def same_size(frames: list[Path]) -> bool:
    """True when every frame has the same width and height (so one camera took them all)."""
    sizes = set()
    for f in frames:
        img = cv2.imread(str(f))
        if img is not None:
            sizes.add(img.shape[:2])
    return len(sizes) <= 1


def estimate_poses(frames: list[Path], work_dir: Path, progress: Progress, single_camera: bool = True):
    """Run COLMAP SfM. Returns (pycolmap.Reconstruction, images_dir).

    `single_camera` is right for a video (one phone, one lens). Photos can come in mixed shapes (portrait
    and landscape) or zooms, which one shared camera cannot describe, so each gets its own."""
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
        camera_mode=pycolmap.CameraMode.SINGLE if single_camera else pycolmap.CameraMode.PER_IMAGE,
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
    """Locate the Brush trainer: BRUSH_PATH, then anywhere under backend/tools/, then PATH.

    The search is recursive because Windows zip tools often extract into a nested folder
    (tools/brush-app-.../brush-app-.../brush_app.exe)."""
    env = os.environ.get("BRUSH_PATH")
    if env and Path(env).exists():
        return env
    tools = BASE_DIR / "tools"
    if tools.exists():
        for p in sorted(tools.rglob("brush_app*")):
            if p.is_file() and p.suffix.lower() in ("", ".exe") and os.access(p, os.X_OK):
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


class _TrainerFailed(Exception):
    def __init__(self, code: int, tail: str):
        super().__init__(tail)
        self.code, self.tail = code, tail


def explain_trainer_failure(code: int, tail: str) -> str:
    """Turn a crashed trainer into advice a person can follow."""
    low = tail.lower()
    if code in (3221225781, 3221225785, -1073741515) or "vcruntime" in low or "msvcp" in low:
        return (
            "The 3D trainer could not start because a Windows runtime library is missing. "
            "Install the 'Microsoft Visual C++ Redistributable (x64)' and process the video again."
        )
    if any(w in low for w in ("out of memory", "outofmemory", "oom", "allocation", "buffer size", "max_buffer", "device lost")):
        return (
            "The graphics card ran out of memory while building the 3D model. Close other programs and process the "
            "video again. On a 4 GB card, set SPLAT_MAX_SPLATS=300000 and SPLAT_MAX_RESOLUTION=800 in backend/.env."
        )
    if any(w in low for w in ("adapter", "no suitable", "vulkan", "dx12", "metal", "surface")):
        return (
            "No compatible graphics adapter was found for the 3D trainer. Update the graphics driver and, on a laptop "
            "with two GPUs, make sure Windows uses the NVIDIA GPU for this app "
            "(Settings > System > Display > Graphics). Run `python backend/scripts/doctor.py --gpu-test` for details."
        )
    snippet = tail.strip().splitlines()[-1][:160] if tail.strip() else f"exit code {code}"
    return f"The 3D trainer stopped unexpectedly ({snippet})."


def _run_brush(brush: str, dataset: Path, out_ply: Path, progress: Progress, steps: int, max_resolution: int, max_splats: int) -> Path:
    export_dir = out_ply.parent / f".{out_ply.stem}_export"
    shutil.rmtree(export_dir, ignore_errors=True)
    export_dir.mkdir(parents=True)

    every = max(1000, steps // 6)
    cmd = [
        brush, str(dataset),
        "--total-steps", str(steps),
        "--max-resolution", str(max_resolution),
        "--max-splats", str(max_splats),
        # Grow splats where the picture is still wrong (a lower threshold than Brush's default
        # finds more detail), then stop growing at 55% of the run and spend the rest polishing.
        # Brush's own default never stops growing in a run shorter than 30000 steps.
        "--growth-grad-threshold", "0.00002",
        "--growth-stop-iter", str(int(steps * GROWTH_STOP_FRACTION)),
        # The browser viewer shows base colour only, so view-dependent colour (spherical
        # harmonics) would be trained and then thrown away. Skipping it also cuts GPU
        # memory and time, which matters on a 4 GB laptop card.
        "--sh-degree", "0",
        "--export-path", str(export_dir),
        "--export-name", "export_{iter}.ply",
        "--export-every", str(every),
    ]
    env = dict(os.environ)
    env.setdefault("WGPU_POWER_PREF", "high")  # prefer the discrete GPU on laptops with two
    progress("train", 0.0, "Training the 3D model")
    log_path = dataset.parent / "brush.log"
    started = time.time()
    with open(log_path, "wb") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env)
        while proc.poll() is None:
            time.sleep(3)
            latest = _latest_export(export_dir)
            if latest:
                frac = min(latest[0] / steps, 0.98)
                progress("train", frac, f"Training the 3D model ({int(frac * 100)}%)")
            if time.time() - started > TRAIN_TIMEOUT_MIN * 60:
                proc.kill()
                raise ReconstructionError("The 3D model took too long to train and was stopped.")
    if proc.returncode != 0:
        raise _TrainerFailed(proc.returncode, log_path.read_text(errors="ignore")[-2000:])

    latest = _latest_export(export_dir)
    if not latest:
        raise ReconstructionError("The 3D trainer finished but wrote no model file.")
    out_ply.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(latest[1]), out_ply)
    shutil.rmtree(export_dir, ignore_errors=True)
    progress("train", 1.0, "3D model ready")
    return out_ply


def train_splat(
    dataset: Path,
    out_ply: Path,
    progress: Progress,
    steps: int = 12000,
    max_resolution: int = 1280,
    max_splats: int = 1_000_000,
) -> Path:
    """Train with Brush. Brush writes `export_<iteration>.ply` every few thousand
    steps, which doubles as a progress indicator.

    If the trainer crashes (typically a small GPU running out of memory) it is
    retried once with much lighter settings before giving up.
    """
    brush = find_brush()
    if not brush:
        raise ReconstructionError(
            "The 3D trainer (Brush) is not installed on this computer. Download it from "
            "https://github.com/ArthurBrussee/brush/releases into backend/tools/ (see the README, 'Real 3D models')."
        )
    attempts = [
        (steps, max_resolution, max_splats),
        (min(steps, 7000), min(max_resolution, 800), min(max_splats, 300_000)),
    ]
    failure: _TrainerFailed | None = None
    for n, (s, res, splats) in enumerate(attempts):
        try:
            return _run_brush(brush, dataset, out_ply, progress, s, res, splats)
        except _TrainerFailed as exc:
            failure = exc
            if n + 1 < len(attempts):
                progress("train", 0.0, "Retrying with lower graphics-memory settings")
    raise ReconstructionError(explain_trainer_failure(failure.code, failure.tail))
