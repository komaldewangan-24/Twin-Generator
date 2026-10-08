import os
import shutil
import subprocess
from pathlib import Path

FFMPEG = "ffmpeg"


def find_ffmpeg() -> str:
    """Locate ffmpeg: explicit env override, PATH, then common WinGet install dirs."""
    env = os.environ.get("FFMPEG_PATH")
    if env and Path(env).exists():
        return env

    on_path = shutil.which(FFMPEG)
    if on_path:
        return on_path

    try:  # bundled binary from the imageio-ffmpeg package (see requirements.txt)
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - package missing or no binary for this platform
        pass

    root = Path(os.environ.get("LOCALAPPDATA", "")).joinpath("Microsoft", "WinGet", "Packages")
    if root.exists():
        for candidate in root.rglob("ffmpeg.exe"):
            return str(candidate)

    raise RuntimeError("ffmpeg not found - install it or set FFMPEG_PATH env var")


def extract_frames(video_path: str, frames_dir: str, fps: int = 4, short_side: int = 720) -> int:
    """Extract a compact set of analysis frames using FFmpeg.

    Returns the number of frames written. Raises RuntimeError with a short
    message on any failure (missing ffmpeg, bad video, etc).
    """
    frames = Path(frames_dir)
    frames.mkdir(parents=True, exist_ok=True)

    for stale in frames.glob("*.jpg"):
        stale.unlink()

    cmd = [
        find_ffmpeg(),
        "-y",
        "-i",
        video_path,
        "-vf",
        # Scale by the SHORT side so portrait phone video (the usual case) keeps
        # 720x1280 instead of shrinking to 405x720. ffmpeg has already applied the
        # phone's rotation flag at this point.
        f"scale=w='if(gt(iw,ih),-2,{short_side})':h='if(gt(iw,ih),{short_side},-2)',fps={fps}",
        str(frames / "frame_%05d.jpg"),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        raise RuntimeError("ffmpeg not found on PATH - install it to process videos")
    except subprocess.TimeoutExpired:
        raise RuntimeError("frame extraction timed out")

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-400:]}")

    count = len(list(frames.glob("*.jpg")))
    if count == 0:
        raise RuntimeError("no frames extracted - is the file a valid video?")
    return count