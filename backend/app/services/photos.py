"""Photos instead of a video.

The 3D engine only needs overlapping pictures of a place; a video is just a convenient way to get many.
Photos go through exactly the same steps as video frames, so this turns them into the same thing:
a folder of `frame_00001.jpg`, ... scaled so the short side is FRAME_SHORT_SIDE pixels. Phone photos
come rotated by a flag in the file (EXIF), which is applied here, and iPhone photos are usually HEIC,
which is read when `pillow-heif` is installed.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.extractor import FRAME_SHORT_SIDE

try:  # HEIC is what an iPhone saves by default
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC_SUPPORTED = True
except Exception:  # noqa: BLE001 - optional dependency, or no wheel for this platform
    HEIC_SUPPORTED = False

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")
MIN_PHOTOS = 15          # fewer cannot be linked into a camera path reliably
MAX_PHOTOS = 300         # about 240 are used; more only makes the wait longer
MAX_PHOTO_BYTES = 80 * 1024 * 1024


def is_photo_name(name: str) -> bool:
    return Path(name or "").suffix.lower() in PHOTO_EXTENSIONS


def _natural_key(path: Path):
    """IMG_2 before IMG_10: photos are linked in the order they were taken."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def prepare_photos(photos_dir: str | Path, frames_dir: str | Path, short_side: int = FRAME_SHORT_SIDE) -> int:
    """Write one `frame_NNNNN.jpg` per readable photo and return how many there are.

    Photos that cannot be read are skipped; if fewer than MIN_PHOTOS remain the scan cannot be built and
    the message says why."""
    frames = Path(frames_dir)
    frames.mkdir(parents=True, exist_ok=True)
    for stale in frames.glob("*.jpg"):
        stale.unlink()

    sources = sorted((p for p in Path(photos_dir).iterdir() if p.is_file() and is_photo_name(p.name)), key=_natural_key)
    written = 0
    unreadable: list[str] = []
    for path in sources:
        try:
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img)          # the phone's "rotate this one" flag
                img = img.convert("RGB")
                w, h = img.size
                if min(w, h) < 64:
                    raise ValueError("too small")
                scale = short_side / min(w, h)               # both ways: very small photos are scaled up, like video frames
                img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
                written += 1
                img.save(frames / f"frame_{written:05d}.jpg", quality=93)
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            unreadable.append(path.name)

    if written < MIN_PHOTOS:
        why = f" {len(unreadable)} could not be read ({', '.join(unreadable[:3])}{'...' if len(unreadable) > 3 else ''})." if unreadable else ""
        heic = " iPhone HEIC photos need the pillow-heif package; export them as JPG." if unreadable and not HEIC_SUPPORTED and any(n.lower().endswith((".heic", ".heif")) for n in unreadable) else ""
        raise RuntimeError(f"Only {written} usable photos, and at least {MIN_PHOTOS} are needed to build a 3D model.{why}{heic}")
    return written
