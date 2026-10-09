"""Export the object-detector model (YOLOv8s) to ONNX, once.

    python scripts/setup_detector.py          # skips if backend/models/yolov8s.onnx exists
    python scripts/setup_detector.py --force

Why a script: the exporter (ultralytics + PyTorch) is large and conflicts with this app's own
packages, so it runs in a temporary virtual environment that is deleted afterwards. The app
itself only needs the small ONNX file. Needs internet and a few hundred MB of free disk for
the one-time export. Works on Windows, macOS and Linux.
"""

import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

MODELS = Path(__file__).resolve().parent.parent / "models"
TARGET = MODELS / "yolov8s.onnx"


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    if TARGET.exists() and "--force" not in sys.argv:
        print(f"Already present: {TARGET} ({TARGET.stat().st_size / 1e6:.0f} MB). Use --force to redo it.")
        return
    MODELS.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="twin_detector_"))
    try:
        env_dir = work / "venv"
        venv.EnvBuilder(with_pip=True).create(env_dir)
        bin_dir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
        py = str(bin_dir / ("python.exe" if sys.platform == "win32" else "python"))
        run([py, "-m", "pip", "install", "--quiet", "ultralytics", "onnx"], work)
        run([py, "-m", "ultralytics", "export", "model=yolov8s.pt", "format=onnx"], work)
        exported = work / "yolov8s.onnx"
        if not exported.exists():
            sys.exit("Export finished but yolov8s.onnx was not produced.")
        shutil.copyfile(exported, TARGET)
        print(f"Installed {TARGET}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
