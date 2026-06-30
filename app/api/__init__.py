"""JSON API blueprint.

The web pages are server-rendered, but all data mutations go through this API
so the same endpoints serve both the online UI and the offline sync engine.
"""
from flask import Blueprint, jsonify

api_bp = Blueprint("api", __name__)


def ok(payload=None, status: int = 200):
    return jsonify({"ok": True, "data": payload}), status


def err(message: str, status: int = 400, **extra):
    body = {"ok": False, "error": message}
    body.update(extra)
    return jsonify(body), status


# Import route modules to register them on the blueprint.
from . import resources  # noqa: E402,F401
from . import dashboard  # noqa: E402,F401
from . import sync  # noqa: E402,F401
from . import photos  # noqa: E402,F401
