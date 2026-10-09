"""Download and install the Brush 3D trainer for this computer (Windows, macOS or Linux).

    python scripts/install_brush.py                 # download, verify, unpack into backend/tools/
    python scripts/install_brush.py --file C:\\path\\to\\brush-app-....zip   # use a file you downloaded yourself

Fetches the official release from https://github.com/ArthurBrussee/brush/releases, checks its
SHA-256 checksum and unpacks it into backend/tools/. Brush needs a graphics card with
Vulkan, DirectX 12 or Metal; it does not need NVIDIA.

If the download keeps failing (slow or blocked connection, antivirus, proxy), download the file
in your browser, save it inside backend/tools/ and run this script again: it picks it up.
"""

import hashlib
import http.client
import platform
import re
import socket
import ssl
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

VERSION = "v0.3.0"
BASE = f"https://github.com/ArthurBrussee/brush/releases/download/{VERSION}"
TOOLS = Path(__file__).resolve().parent.parent / "tools"
ATTEMPTS = 8
SOCKET_TIMEOUT_S = 30


class InstallError(Exception):
    """A failure with a message that tells the person what to do."""


def release_base() -> str:
    import os

    return os.environ.get("TWIN_BRUSH_BASE", BASE)  # overridable so tests need no internet


def asset_name() -> str:
    system, machine = platform.system(), platform.machine().lower()
    if system == "Windows":
        return "brush-app-x86_64-pc-windows-msvc.zip"
    if system == "Darwin":
        if machine in ("arm64", "aarch64"):
            return "brush-app-aarch64-apple-darwin.tar.xz"
        raise InstallError("Brush has no build for Intel Macs. Use the demo scan, or train on another computer.")
    if system == "Linux":
        return "brush-app-x86_64-unknown-linux-gnu.tar.xz"
    raise InstallError(f"No Brush build for {system} {machine}.")


# ---------------------------------------------------------------------------- network


def _ssl_contexts():
    """The system certificates first; if the connection is intercepted by an antivirus or an old
    Windows store makes validation fail, retry with the certifi bundle that httpx ships with."""
    yield ssl.create_default_context()
    try:
        import certifi

        yield ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return


def open_url(req: urllib.request.Request):
    last: Exception | None = None
    for ctx in _ssl_contexts():
        try:
            return urllib.request.urlopen(req, timeout=SOCKET_TIMEOUT_S, context=ctx)  # noqa: S310 - https URL
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, ssl.SSLError):
                last = exc  # try the next certificate source
                continue
            raise
        except ssl.SSLError as exc:
            last = exc
            continue
    raise InstallError(
        "Could not make a secure connection to GitHub (certificate problem). If an antivirus or "
        f"proxy is inspecting HTTPS traffic, pause it for this download. ({last})"
    )


def download(url: str, dest: Path) -> None:
    """Download with resume: a dropped connection continues where it stopped."""
    part = dest.with_name(dest.name + ".part")
    last_error = "unknown error"
    for attempt in range(1, ATTEMPTS + 1):
        have = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            with open_url(urllib.request.Request(url, headers=headers)) as r:
                resumed = have > 0 and getattr(r, "status", 200) == 206
                if have and not resumed:
                    have = 0  # the server ignored Range; start over
                total = have + int(r.headers.get("Content-Length", 0))
                done = have
                with open(part, "ab" if resumed else "wb") as f:
                    while chunk := r.read(1 << 20):
                        f.write(chunk)
                        done += len(chunk)
                        if total:
                            print(f"\r  {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
                print()
                if total and done < total:
                    raise ConnectionError(f"connection closed after {done} of {total} bytes")
            part.replace(dest)
            return
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and have:  # asked for bytes past the end: already complete
                part.replace(dest)
                return
            if 400 <= exc.code < 500 and exc.code != 429:
                raise InstallError(f"GitHub answered {exc.code} for {url}. The release may have moved.") from exc
            last_error = f"server error {exc.code}"
        except InstallError:
            raise
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as exc:
            last_error = getattr(exc, "reason", None) or exc
        wait = min(2 ** attempt, 20)
        print(f"\n  download interrupted ({last_error}); retrying in {wait}s (attempt {attempt} of {ATTEMPTS})")
        time.sleep(wait)
    raise InstallError(f"The download kept failing ({last_error}).")


def expected_checksum(name: str) -> str | None:
    try:
        with open_url(urllib.request.Request(f"{release_base()}/{name}.sha256")) as r:
            text = r.read().decode("utf-8", errors="ignore")
    except (InstallError, urllib.error.URLError, OSError):
        return None
    m = re.search(r"\b[0-9a-fA-F]{64}\b", text)  # tolerant of BOMs, '*file' and CRLF
    return m.group(0).lower() if m else None


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------- unpack


def _own_folder(entries: list[tuple[str, bool]], archive: Path, dest_dir: Path) -> Path:
    """The Windows zip has brush_app.exe at its root, with no containing folder. Unpack such
    archives into a folder of their own instead of scattering README/LICENSE into tools/.
    `entries` are (path, is_directory) pairs."""
    norm = [(n.replace("\\", "/").strip("/"), is_dir) for n, is_dir in entries]
    tops = {n.split("/")[0] for n, _ in norm if n}
    has_root_files = any("/" not in n and not is_dir for n, is_dir in norm if n)
    if len(tops) == 1 and not has_root_files:
        return dest_dir
    stem = archive.name.removesuffix(".zip").removesuffix(".tar.xz")
    return dest_dir / stem


def unpack(archive: Path, dest_dir: Path) -> None:
    try:
        if archive.name.endswith(".zip"):
            with zipfile.ZipFile(archive) as z:
                target = _own_folder([(i.filename, i.is_dir()) for i in z.infolist()], archive, dest_dir)
                target.mkdir(parents=True, exist_ok=True)
                z.extractall(target)
        else:
            with tarfile.open(archive) as t:
                target = _own_folder([(m.name, m.isdir()) for m in t.getmembers()], archive, dest_dir)
                target.mkdir(parents=True, exist_ok=True)
                try:
                    t.extractall(target, filter="data")  # safe extraction (Python 3.11.4+)
                except TypeError:
                    t.extractall(target)  # noqa: S202 - older Python; archive is checksum-verified
    except (zipfile.BadZipFile, tarfile.TarError, EOFError) as exc:
        archive.unlink(missing_ok=True)
        raise InstallError(f"The downloaded file is damaged ({exc}). It was deleted: run this script again.") from exc
    except PermissionError as exc:
        raise InstallError(
            "Windows would not let the files be written. This is usually antivirus (Windows Security) "
            f"quarantining the trainer. Add an exclusion for the folder {dest_dir} and run this again. ({exc})"
        ) from exc


def find_exe(dest_dir: Path) -> Path | None:
    for p in sorted(dest_dir.rglob("brush_app*")):
        if p.is_file() and p.suffix.lower() in ("", ".exe"):
            return p
    return None


def main() -> None:
    args = sys.argv[1:]
    dest_dir = Path(args[args.index("--dest") + 1]) if "--dest" in args else TOOLS
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = asset_name()

    if "--file" in args:
        archive = Path(args[args.index("--file") + 1]).expanduser()
        if not archive.is_file():
            raise InstallError(f"File not found: {archive}")
    else:
        archive = dest_dir / name
        if archive.is_file():
            print(f"Using the file you already downloaded: {archive}")
        else:
            download(f"{release_base()}/{name}", archive)

    expected = expected_checksum(name)
    if expected is None:
        print("Warning: could not fetch the checksum, so the file was not verified.")
    else:
        actual = sha256_of(archive)
        if actual != expected:
            if "--file" not in args:
                archive.unlink(missing_ok=True)
            raise InstallError(
                "The file does not match the official checksum, so it was not installed "
                f"(a partial or altered download).\n  expected {expected}\n  got      {actual}\nDownload it again."
            )
        print("Checksum OK")

    unpack(archive, dest_dir)
    if "--file" not in args:
        archive.unlink(missing_ok=True)

    exe = find_exe(dest_dir)
    if not exe:
        raise InstallError(
            "Unpacked, but brush_app was not found. If you are on Windows, antivirus may have removed it: "
            f"add an exclusion for {dest_dir} and run this again."
        )
    exe.chmod(exe.stat().st_mode | 0o111)
    try:
        version = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        version = ""
    if not version:
        print(
            "Installed, but the program did not start. On Windows install the 'Microsoft Visual C++ "
            "Redistributable (x64)' (search for it on Microsoft's site), then run: python scripts/doctor.py"
        )
    else:
        print(f"Installed: {exe} ({version})")
    print("Next: python scripts/doctor.py --gpu-test")


if __name__ == "__main__":
    try:
        main()
    except InstallError as exc:
        name = "the Brush archive for your system"
        try:
            name = asset_name()
        except InstallError:
            pass
        print(f"\nProblem: {exc}\n")
        print("Manual way, if the download keeps failing:")
        print(f"  1. Open {release_base()}/{name} in your browser (or see https://github.com/ArthurBrussee/brush/releases).")
        print(f"  2. Save the file inside this folder: {TOOLS}")
        print("  3. Run again: python scripts/install_brush.py")
        sys.exit(1)
