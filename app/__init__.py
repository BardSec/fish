"""Fishing Atlas application factory."""
import os

from flask import Flask

from config import Config
from .extensions import db, migrate


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Ensure instance + upload folders exist.
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Alembic/migrate and create_all can see them.
    from . import models  # noqa: F401

    # Blueprints
    from .views import pages
    from .api import api_bp

    app.register_blueprint(pages)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Expose select map config to every template.
    @app.context_processor
    def inject_map_config() -> dict:
        return {
            "MAP_CONFIG": {
                "tileUrl": app.config["MAP_TILE_URL"],
                "attribution": app.config["MAP_TILE_ATTRIBUTION"],
                "lat": app.config["MAP_DEFAULT_LAT"],
                "lng": app.config["MAP_DEFAULT_LNG"],
                "zoom": app.config["MAP_DEFAULT_ZOOM"],
            }
        }

    # Create tables on first run if no migrations have been applied yet.
    # (Migrations remain the source of truth in production; this keeps the
    # dev/Docker first-boot experience friction-free.)
    with app.app_context():
        db.create_all()

    register_cli(app)
    return app


def register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command():
        """Reset and load East Tennessee sample data."""
        from prisma.seed import seed
        seed()
