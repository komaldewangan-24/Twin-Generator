"""Export the object-detector models to ONNX, once.

    python scripts/setup_detector.py                 # YOLOv8s: furniture and common objects
    python scripts/setup_detector.py --open-vocab    # YOLO-World: doors, windows, lights, counters...
    python scripts/setup_detector.py --force         # redo it even if the file exists

Why a script: the exporters (ultralytics + PyTorch, and OpenAI's CLIP text encoder for the
open-vocabulary model) are large and conflict with this app's own packages, so they run in a
temporary virtual environment that is deleted afterwards. The app itself only needs the
small ONNX files. Needs internet and a few hundred MB of free disk for the one-time export
(the open-vocabulary model downloads about 370 MB). Works on Windows, macOS and Linux.

Licence note: ultralytics and YOLO-World are AGPL-3.0 / GPL-3.0. Fine for an open-source
academic project; check before shipping them inside a closed product.
"""

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODELS = HERE.parent / "models"
FURNITURE = MODELS / "yolov8s.onnx"
OPEN_VOCAB = MODELS / "open_vocab.onnx"
CLIP_REQUIREMENT = "git+https://github.com/ultralytics/CLIP.git"


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def temp_env(work: Path) -> str:
    env_dir = work / "venv"
    venv.EnvBuilder(with_pip=True).create(env_dir)
    bin_dir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    return str(bin_dir / ("python.exe" if sys.platform == "win32" else "python"))


def export_furniture(work: Path) -> None:
    py = temp_env(work)
    run([py, "-m", "pip", "install", "--quiet", "ultralytics", "onnx"], work)
    run([py, "-m", "ultralytics", "export", "model=yolov8s.pt", "format=onnx"], work)
    exported = work / "yolov8s.onnx"
    if not exported.exists():
        sys.exit("Export finished but yolov8s.onnx was not produced.")
    shutil.copyfile(exported, FURNITURE)
    print(f"Installed {FURNITURE}")


def export_open_vocab(work: Path) -> None:
    if shutil.which("git") is None:
        sys.exit("Git is needed to install the CLIP text encoder. Install Git from https://git-scm.com and run this again.")
    py = temp_env(work)
    run([py, "-m", "pip", "install", "--quiet", "ultralytics", "onnx", "onnxslim", CLIP_REQUIREMENT], work)
    run([py, str(HERE / "export_open_vocab.py")], work)
    if not OPEN_VOCAB.exists():
        sys.exit("Export finished but open_vocab.onnx was not produced.")
    print(f"Installed {OPEN_VOCAB}")


def main() -> None:
    force = "--force" in sys.argv
    target, job = (OPEN_VOCAB, export_open_vocab) if "--open-vocab" in sys.argv else (FURNITURE, export_furniture)
    if target.exists() and not force:
        print(f"Already present: {target} ({target.stat().st_size / 1e6:.0f} MB). Use --force to redo it.")
        return
    MODELS.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="twin_detector_"))
    try:
        job(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
