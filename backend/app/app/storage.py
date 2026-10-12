"""Small helpers for saving uploaded profile photos on disk.

Photos are stored in backend/uploads/photos/ and served by FastAPI at /uploads/...
The folder is created automatically and is listed in .gitignore.
"""

import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"
PHOTO_DIR = UPLOAD_DIR / "photos"
PHOTO_URL_PREFIX = "/uploads/photos/"
MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB

PHOTO_DIR.mkdir(parents=True, exist_ok=True)


def detect_image_extension(data: bytes) -> str | None:
    """Look at the first bytes of the file, not the file name the user sent."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_photo(user_id: int, data: bytes, extension: str) -> str:
    """Save the image under a random name and return its public URL path."""
    filename = f"{user_id}_{uuid.uuid4().hex}.{extension}"
    (PHOTO_DIR / filename).write_bytes(data)
    return PHOTO_URL_PREFIX + filename


def delete_photo(photo_url: str | None) -> None:
    """Delete a saved photo. Ignores anything that is not one of our own files."""
    if not photo_url or not photo_url.startswith(PHOTO_URL_PREFIX):
        return
    path = PHOTO_DIR / Path(photo_url).name
    if path.is_file():
        path.unlink()
