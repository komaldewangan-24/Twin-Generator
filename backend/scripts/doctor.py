"""Check that this computer can run the Digital Twin Generator, and say how to fix what can't.

    python scripts/doctor.py               # quick checks
    python scripts/doctor.py --gpu-test    # also trains a tiny 3D model (about 10 to 60 seconds)

If the 3D model does not show up, run this FIRST and send the output to whoever is helping.
Nothing here changes your files except a temporary folder for the GPU test.
"""

import importlib
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results: list[tuple[str, str]] = []


def report(status: str, title: str, detail: str = "") -> None:
    icon = {"OK": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]", "INFO": "[info]"}[status]
    print(f"{icon} {title}")
    for line in detail.strip().splitlines():
        print(f"       {line}")
    results.append((status, title))


def run(cmd: list[str], timeout: int = 20) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (out.stdout + out.stderr).strip()
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------- checks


def check_python() -> None:
    v = sys.version_info
    if v < (3, 11):
        report("FAIL", f"Python {v.major}.{v.minor}", "Python 3.11 or newer is required (3.13 is tested). Install it and recreate the venv.")
    else:
        report("OK", f"Python {v.major}.{v.minor}.{v.micro} on {platform.system()} {platform.machine()}")


def check_packages() -> None:
    needed = {
        "fastapi": "fastapi", "uvicorn": "uvicorn", "sqlalchemy": "sqlalchemy", "email_validator": "email-validator",
        "cv2": "opencv-python-headless", "numpy": "numpy", "sklearn": "scikit-learn", "onnxruntime": "onnxruntime",
        "pycolmap": "pycolmap", "imageio_ffmpeg": "imageio-ffmpeg", "jose": "python-jose", "passlib": "passlib",
    }
    missing = []
    for mod, pkg in needed.items():
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{pkg} ({exc.__class__.__name__}: {str(exc)[:80]})")
    if missing:
        report("FAIL", "Python packages", "Missing or broken:\n" + "\n".join(f"- {m}" for m in missing) + "\nFix: pip install -r requirements.txt")
    else:
        report("OK", "Python packages (all installed)")


def check_ffmpeg() -> None:
    from app.services import extractor

    try:
        path = extractor.find_ffmpeg()
        first = run([path, "-version"]).splitlines()[0:1]
        report("OK", "FFmpeg", f"{path}\n{first[0] if first else ''}")
    except Exception as exc:  # noqa: BLE001
        report("FAIL", "FFmpeg not found", f"{exc}\nFix: pip install imageio-ffmpeg (or install FFmpeg and put it on PATH).")


def check_detector() -> None:
    from app.core.config import settings

    path = Path(settings.YOLO_ONNX_PATH)
    if not path.exists():
        report(
            "FAIL", "Object detector model missing",
            f"Expected {path}\nWithout it objects are not detected (the 3D model still builds).\n"
            "Fix:  python scripts/setup_detector.py     (one-time export, takes a few minutes)",
        )
        return
    try:
        import onnxruntime as ort

        ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        report("OK", f"Object detector model ({path.name}, {path.stat().st_size / 1e6:.0f} MB)")
    except Exception as exc:  # noqa: BLE001
        report("FAIL", "Object detector model will not load", f"{path}\n{exc.__class__.__name__}: {str(exc)[:160]}")


def check_open_vocab() -> None:
    """Optional: without it the app finds furniture but not doors, windows or lights."""
    from app.core.config import settings

    base = Path(settings.YOLO_ONNX_PATH).parent
    if (base / "open_vocab.onnx").exists() and (base / "open_vocab.json").exists():
        report("OK", "Doors, windows and lights model (open_vocab.onnx)")
    else:
        report(
            "INFO", "Doors and windows are not detected (optional model not installed)",
            "To add them, with an internet connection:  python scripts/setup_detector.py --open-vocab\n"
            "(about 370 MB of one-time downloads; it needs Git installed)",
        )


def find_brush() -> str | None:
    from app.services import reconstruct

    return reconstruct.find_brush()


def check_brush() -> str | None:
    brush = find_brush()
    if not brush:
        report(
            "FAIL", "3D trainer (Brush) not installed",
            "This is the most common reason no 3D model appears for a new video.\n"
            "Fix:  python scripts/install_brush.py     (downloads and verifies the right build for this computer)\n"
            "Or install it by hand from https://github.com/ArthurBrussee/brush/releases into " + str(ROOT / "tools") + " and set BRUSH_PATH if needed.",
        )
        return None
    version = run([brush, "--version"])
    if not version:
        report("FAIL", "3D trainer found but will not start", f"{brush}\nOn Windows install the 'Microsoft Visual C++ Redistributable (x64)', then retry.")
        return None
    report("OK", "3D trainer (Brush)", f"{brush}\n{version.splitlines()[0]}")
    return brush


def gpu_names() -> list[str]:
    system = platform.system()
    if system == "Windows":
        out = run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"])
        return [l.strip() for l in out.splitlines() if l.strip()]
    if system == "Darwin":
        out = run(["system_profiler", "SPDisplaysDataType"], timeout=30)
        return re.findall(r"Chipset Model:\s*(.+)", out)
    out = run(["sh", "-c", "lspci | grep -iE 'vga|3d|display'"])
    return [l.split(": ", 1)[-1].strip() for l in out.splitlines() if l.strip()]


def check_gpu() -> None:
    names = gpu_names()
    nvidia = run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    detail = "\n".join(names) if names else "Could not list graphics adapters."
    if nvidia:
        detail += f"\nNVIDIA: {nvidia}"
        m = re.search(r"(\d+)\s*MiB", nvidia)
        if m and int(m.group(1)) <= 4096:
            detail += (
                "\nThis card has about 4 GB. If the 3D model fails, set in backend/.env:\n"
                "SPLAT_MAX_SPLATS=300000 and SPLAT_MAX_RESOLUTION=800"
            )
    if len(names) > 1 and any("nvidia" in n.lower() for n in names) and any(re.search(r"intel|amd|radeon", n, re.I) for n in names):
        detail += (
            "\nTwo GPUs found (typical gaming laptop). Make Windows use the NVIDIA one for the browser and for Python:\n"
            "Settings > System > Display > Graphics > add chrome.exe / python.exe > Options > High performance."
        )
    report("INFO", "Graphics", detail)


def check_env() -> None:
    from app.core.config import settings

    env_file = ROOT / ".env"
    if not env_file.exists():
        report("WARN", "backend/.env missing", "Copy .env.example to .env and set JWT_SECRET_KEY (a long random string).")
    elif settings.JWT_SECRET_KEY == "dev-only-secret":
        report("WARN", "JWT_SECRET_KEY not set", "Set it in backend/.env (python -c \"import secrets; print(secrets.token_hex(32))\").")
    else:
        report("OK", "backend/.env (secret key set)")
    if any(ord(ch) > 127 for ch in str(ROOT)):
        report(
            "WARN", "Non-English characters in the project folder path",
            f"{ROOT}\nCOLMAP and Brush can fail on such paths on Windows. Move the project to a plain folder like C:\\twin.",
        )
    for d in (settings.UPLOADS_DIR, settings.SPLATS_DIR):
        try:
            probe = d / ".write-test"
            probe.write_text("x")
            probe.unlink()
        except OSError as exc:
            report("FAIL", f"Cannot write to {d}", str(exc))
            return
    report("OK", "Storage folders are writable")


def check_demo() -> None:
    from app.services import demo

    if demo.available():
        report("OK", "Demo scan present", f"{demo.DEMO_SPLAT.stat().st_size / 1e6:.1f} MB. On the dashboard press 'Demo scan' to see the full app without training.")
    else:
        report("WARN", "Demo scan missing", "backend/demo/ is empty. Run: git pull   (or: python scripts/export_demo.py <project-id>)")


def check_node() -> None:
    node = shutil.which("node")
    if not node:
        report("FAIL", "Node.js not found", "Install Node.js 20.19+ or 22.12+ (the frontend needs it).")
        return
    out = run([node, "--version"])
    m = re.match(r"v(\d+)\.(\d+)", out)
    ok = bool(m) and ((int(m.group(1)), int(m.group(2))) >= (22, 12) or (20, 19) <= (int(m.group(1)), int(m.group(2))) < (21, 0))
    report("OK" if ok else "FAIL", f"Node.js {out}", "" if ok else "Vite 8 needs Node 20.19+ or 22.12+. Update Node.")


def gpu_test(brush: str) -> None:
    from app.services import reconstruct

    dataset = ROOT / "demo" / "gpu_test"
    if not dataset.exists():
        report("WARN", "GPU test data missing", f"{dataset} not found. Run: git pull")
        return
    print("\nTraining a tiny 3D model on your GPU (300 steps)...")
    tmp = Path(tempfile.mkdtemp(prefix="twin_gpu_test_"))
    try:
        staged = tmp / "dataset"
        shutil.copytree(dataset, staged)
        started = time.time()
        reconstruct._run_brush(brush, staged, tmp / "out" / "test.ply", lambda *a: None, 300, 480, 100_000)  # noqa: SLF001
        report("OK", "GPU can train 3D models", f"300 steps took {time.time() - started:.0f} s.")
    except reconstruct._TrainerFailed as exc:  # noqa: SLF001
        report("FAIL", "GPU test failed", reconstruct.explain_trainer_failure(exc.code, exc.tail) + f"\n--- raw output (exit code {exc.code}) ---\n{exc.tail[-600:]}")
    except Exception as exc:  # noqa: BLE001
        report("FAIL", "GPU test failed", f"{exc.__class__.__name__}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    print(f"Digital Twin Generator doctor ({platform.platform()})\n")
    check_python()
    check_packages()
    if results and results[-1][0] == "FAIL":
        print("\nInstall the missing packages first, then run this again.")
        sys.exit(1)
    check_node()
    check_ffmpeg()
    check_detector()
    check_open_vocab()
    brush = check_brush()
    check_gpu()
    check_env()
    check_demo()
    if "--gpu-test" in sys.argv:
        if brush:
            gpu_test(brush)
        else:
            report("WARN", "GPU test skipped", "Install the 3D trainer first.")

    fails = [t for s, t in results if s == "FAIL"]
    print()
    if fails:
        print(f"{len(fails)} problem(s) to fix:")
        for t in fails:
            print(f"  - {t}")
        print("\nThe app still runs without these, but the matching feature will not work. The demo scan always works.")
        sys.exit(1)
    print("Everything needed is in place." + ("" if "--gpu-test" in sys.argv else " Add --gpu-test to also test the graphics card."))


if __name__ == "__main__":
    main()
