"""Photo upload endpoint.

Two intake paths:
* ``multipart/form-data`` with a ``file`` field — used by the online forms.
* JSON ``{"data_url": "data:image/...;base64,...."}`` — used by the offline
  sync engine to upload photos captured while disconnected.

Files are written to ``UPLOAD_FOLDER`` (a Docker volume) and served from
``/static/uploads/<filename>``.
"""
from __future__ import annotations

import base64
import binascii
import os
import uuid

from flask import current_app, request

from . import api_bp, err, ok
from ..extensions import db
from ..models import Photo

_ALLOWED_EXT = {"png", "jpg", "jpeg", "gif", "webp", "heic"}
_MIME_EXT = {
    "image/png": "png", "image/jpeg": "jpg", "image/gif": "gif",
    "image/webp": "webp", "image/heic": "heic",
}


def _save_bytes(raw: bytes, ext: str) -> tuple[str, str]:
    fname = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], fname)
    with open(path, "wb") as fh:
        fh.write(raw)
    return fname, f"/static/uploads/{fname}"


@api_bp.post("/photos")
def upload_photo():
    body = request.get_json(silent=True) or {} if request.is_json else {}
    trip_id = request.form.get("trip_id") or body.get("trip_id")
    catch_id = request.form.get("catch_id") or body.get("catch_id")
    caption = request.form.get("caption") or body.get("caption")
    photo_id = request.form.get("id") or body.get("id") or None

    fname = url = None

    if "file" in request.files:
        f = request.files["file"]
        ext = (f.filename.rsplit(".", 1)[-1] if "." in f.filename else "").lower()
        if ext not in _ALLOWED_EXT:
            return err(f"unsupported file type: .{ext}")
        fname, url = _save_bytes(f.read(), ext)
    elif request.is_json:
        data_url = body.get("data_url", "")
        if not data_url.startswith("data:"):
            return err("expected a data: URL")
        try:
            header, b64 = data_url.split(",", 1)
            mime = header.split(";")[0][5:]
            ext = _MIME_EXT.get(mime, "png")
            raw = base64.b64decode(b64)
        except (ValueError, binascii.Error):
            return err("could not decode data URL")
        fname, url = _save_bytes(raw, ext)
    else:
        return err("no file or data_url provided")

    photo = Photo(
        id=photo_id,
        trip_id=trip_id or None,
        catch_id=catch_id or None,
        filename=fname,
        url=url,
        caption=caption,
    )
    db.session.add(photo)
    db.session.commit()
    return ok(photo.to_dict(), 201)


@api_bp.delete("/photos/<photo_id>")
def delete_photo(photo_id):
    photo = db.session.get(Photo, photo_id)
    if not photo:
        return err("Photo not found", 404)
    # Best-effort file cleanup.
    if photo.filename:
        try:
            os.remove(os.path.join(current_app.config["UPLOAD_FOLDER"], photo.filename))
        except OSError:
            pass
    db.session.delete(photo)
    db.session.commit()
    return ok({"id": photo_id})
