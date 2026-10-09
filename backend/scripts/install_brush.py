"""Download and install the Brush 3D trainer for this computer (Windows, macOS or Linux).

    python scripts/install_brush.py

Fetches the official release from https://github.com/ArthurBrussee/brush/releases, checks its
SHA-256 checksum and unpacks it into backend/tools/. Brush needs a graphics card with
Vulkan, DirectX 12 or Metal; it does not need NVIDIA.
"""

import hashlib
import platform
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "v0.3.0"
BASE = f"https://github.com/ArthurBrussee/brush/releases/download/{VERSION}"
TOOLS = Path(__file__).resolve().parent.parent / "tools"


def asset_name() -> str:
    system, machine = platform.system(), platform.machine().lower()
    if system == "Windows":
        return "brush-app-x86_64-pc-windows-msvc.zip"
    if system == "Darwin":
        if machine in ("arm64", "aarch64"):
            return "brush-app-aarch64-apple-darwin.tar.xz"
        sys.exit("Brush has no build for Intel Macs. Use the demo scan, or train on another computer.")
    if system == "Linux":
        return "brush-app-x86_64-unknown-linux-gnu.tar.xz"
    sys.exit(f"No Brush build for {system} {machine}.")


def download(url: str, dest: Path) -> None:
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as f:  # noqa: S310 - fixed https URL
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e6:5.1f} / {total / 1e6:.1f} MB", end="", flush=True)
    print()


def main() -> None:
    dest_dir = Path(sys.argv[sys.argv.index("--dest") + 1]) if "--dest" in sys.argv else TOOLS
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = asset_name()
    archive = dest_dir / name
    download(f"{BASE}/{name}", archive)

    expected = urllib.request.urlopen(f"{BASE}/{name}.sha256", timeout=30).read().decode().split()[0].lower()  # noqa: S310
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        archive.unlink(missing_ok=True)
        sys.exit(f"Checksum mismatch, download deleted.\n  expected {expected}\n  got      {actual}")
    print("Checksum OK")

    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest_dir)
    else:
        with tarfile.open(archive) as t:
            try:
                t.extractall(dest_dir, filter="data")  # safe extraction (Python 3.11.4+)
            except TypeError:
                t.extractall(dest_dir)  # noqa: S202 - older Python; archive is checksum-verified
    archive.unlink()

    found = sorted(dest_dir.rglob("brush_app*"))
    exe = next((p for p in found if p.is_file() and p.suffix.lower() in ("", ".exe")), None)
    if not exe:
        sys.exit("Unpacked, but brush_app was not found. Look inside " + str(dest_dir))
    exe.chmod(exe.stat().st_mode | 0o111)
    print(f"Installed: {exe}\nNext: python scripts/doctor.py --gpu-test")


if __name__ == "__main__":
    main()
