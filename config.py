"""Application configuration, loaded from environment variables.

All runtime configuration is read from the environment (see ``.env.example``).
A ``.env`` file in the project root is loaded automatically in development.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root if present (no-op in production if absent).
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _default_sqlite_uri() -> str:
    """SQLite file lives in the Flask ``instance/`` folder by default.

    In Docker this folder is mounted as a volume so the database survives
    container restarts.
    """
    instance_dir = BASE_DIR / "instance"
    instance_dir.mkdir(exist_ok=True)
    return f"sqlite:///{instance_dir / 'fishing_atlas.db'}"


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

    # Database. Defaults to a local SQLite file; override with DATABASE_URL.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _default_sqlite_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Uploaded photos are written here and served as static files.
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", str(BASE_DIR / "app" / "static" / "uploads")
    )
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))

    # Map configuration. We use Leaflet + OpenStreetMap, which needs no API key.
    # These values are passed to the client so the map can be re-themed or
    # pointed at a different tile server without touching code.
    MAP_TILE_URL = os.environ.get(
        "MAP_TILE_URL", "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    )
    MAP_TILE_ATTRIBUTION = os.environ.get(
        "MAP_TILE_ATTRIBUTION",
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    )
    # Default map center (East Tennessee — Townsend / Little River area).
    MAP_DEFAULT_LAT = float(os.environ.get("MAP_DEFAULT_LAT", 35.6754))
    MAP_DEFAULT_LNG = float(os.environ.get("MAP_DEFAULT_LNG", -83.7563))
    MAP_DEFAULT_ZOOM = int(os.environ.get("MAP_DEFAULT_ZOOM", 11))
