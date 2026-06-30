"""Server-rendered page routes and PWA asset routes."""
from flask import Blueprint, Response, current_app, render_template, send_from_directory

from .constants import (
    CLOUD_COVER, COMMON_SPECIES, FISHING_TYPES, MOON_PHASES, SPOT_TYPES,
    WATER_CLARITY, WATER_LEVELS,
)
from .models import Catch, MapPin, Trip, WaterBody

pages = Blueprint("pages", __name__)


def _form_choices() -> dict:
    return {
        "fishing_types": FISHING_TYPES,
        "spot_types": SPOT_TYPES,
        "water_clarity": WATER_CLARITY,
        "water_levels": WATER_LEVELS,
        "cloud_cover": CLOUD_COVER,
        "moon_phases": MOON_PHASES,
        "species": COMMON_SPECIES,
        "water_bodies": [w.name for w in WaterBody.query.order_by(WaterBody.name).all()],
    }


@pages.get("/")
def dashboard():
    return render_template("dashboard.html", active="dashboard")


@pages.get("/trips")
def trips():
    return render_template("trips.html", active="trips")


@pages.get("/trips/new")
def trip_new():
    return render_template("trip_form.html", active="trips", choices=_form_choices())


@pages.get("/trips/<trip_id>")
def trip_detail(trip_id):
    return render_template("trip_detail.html", active="trips", trip_id=trip_id,
                           choices=_form_choices())


@pages.get("/trips/<trip_id>/edit")
def trip_edit(trip_id):
    return render_template("trip_form.html", active="trips", trip_id=trip_id,
                           choices=_form_choices())


@pages.get("/catches")
def catches():
    return render_template("catches.html", active="catches")


@pages.get("/map")
def map_page():
    return render_template("map.html", active="map", choices=_form_choices())


@pages.get("/pins")
def pins():
    return render_template("pins.html", active="pins", choices=_form_choices())


@pages.get("/settings")
def settings():
    return render_template("settings.html", active="settings")


@pages.get("/offline")
def offline():
    return render_template("offline.html", active=None)


# --- PWA assets ---------------------------------------------------------------

@pages.get("/sw.js")
def service_worker():
    """Serve the service worker from the site root so its scope is the whole app."""
    resp = send_from_directory(current_app.static_folder, "sw.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Content-Type"] = "application/javascript"
    return resp


@pages.get("/manifest.webmanifest")
def manifest():
    resp = send_from_directory(current_app.static_folder, "manifest.webmanifest")
    resp.headers["Content-Type"] = "application/manifest+json"
    return resp


@pages.get("/static/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
