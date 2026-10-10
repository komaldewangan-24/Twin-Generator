import os
import re
import shutil
import subprocess
from pathlib import Path

FFMPEG = "ffmpeg"

# Frames (from a video or from photos) are scaled so the SHORT side is this many pixels.
FRAME_SHORT_SIDE = 720

# How many frames the camera-path and 3D steps are given, about. Frames closer together link up more easily:
# on the playroom sample the share of frames COLMAP could place in 3D was 2 of 28 with every 8th frame, 8 of 38
# with every 6th, 54% with every 4th, 83% with every 3rd and 89% with every 2nd. A short phone clip is the same
# scene moving faster, so it is sampled more densely than a long one. On a 10 second pan, 12 frames per second
# instead of 4 gave a 3D model that predicted frames it had not seen 1.1 dB better (SSIM 0.845 against 0.799).
TARGET_FRAMES = 240
MIN_FPS, MAX_FPS = 4, 12


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


def video_seconds(video_path: str) -> float | None:
    """Length of the video according to ffmpeg, or None when it does not say."""
    try:
        out = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", video_path], capture_output=True, text=True, timeout=60).stderr
    except (OSError, subprocess.TimeoutExpired, RuntimeError):
        return None
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out)
    return int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None


def choose_fps(seconds: float | None) -> int:
    """Frames per second to extract: about TARGET_FRAMES frames in total, between MIN_FPS and MAX_FPS."""
    if not seconds or seconds <= 0:
        return MIN_FPS
    return int(min(MAX_FPS, max(MIN_FPS, round(TARGET_FRAMES / seconds))))


def extract_frames(video_path: str, frames_dir: str, fps: int | None = None, short_side: int = 720) -> int:
    """Extract a compact set of analysis frames using FFmpeg.

    `fps` defaults to choose_fps() for this video's length. Returns the number of frames written.
    Raises RuntimeError with a short message on any failure (missing ffmpeg, bad video, etc).
    """
    if fps is None:
        fps = choose_fps(video_seconds(video_path))
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