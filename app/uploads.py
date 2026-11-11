import os
import secrets

from flask import current_app, send_from_directory

MAX_QR_BYTES = 2 * 1024 * 1024


def detect_image_type(data):
    """'png', 'jpg' or 'webp' judged from the file's first bytes (never its name), else None."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def save_qr_image(file_storage):
    """Save an uploaded QR image. Returns (filename, error_message)."""
    data = file_storage.read(MAX_QR_BYTES + 1)
    if not data:
        return None, "That file is empty."
    if len(data) > MAX_QR_BYTES:
        return None, "The image is too big (2 MB maximum)."
    kind = detect_image_type(data)
    if kind is None:
        return None, "That doesn't look like a PNG, JPG or WebP image."
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    filename = f"gcash_{secrets.token_hex(16)}.{kind}"
    with open(os.path.join(folder, filename), "wb") as f:
        f.write(data)
    return filename, None


def delete_qr_image(filename):
    if not filename:
        return
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], os.path.basename(filename))
    try:
        os.remove(path)
    except OSError:
        pass


def send_qr_image(filename):
    resp = send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
    resp.headers["Cache-Control"] = "private, no-store"
    return resp