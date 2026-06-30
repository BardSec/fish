"""CRUD endpoints for trips, catches, and map pins.

The ``apply_*`` helpers are also reused by the offline sync engine
(:mod:`app.api.sync`), so creation logic lives in one place.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from . import api_bp, err, ok
from ..extensions import db
from ..models import Catch, MapPin, Trip

# --- writable field whitelists -------------------------------------------------

TRIP_FIELDS = {
    "date", "start_time", "end_time", "water_body", "water_body_id",
    "access_point", "general_location", "fishing_type", "target_species",
    "species_caught", "fish_count", "largest_fish", "notes", "air_temp",
    "water_temp", "weather", "cloud_cover", "wind", "water_clarity",
    "water_level", "flow", "recent_rain", "moon_phase", "hatch",
}
CATCH_FIELDS = {
    "trip_id", "map_pin_id", "species", "length", "time_caught", "bait",
    "presentation", "water_type", "kept", "notes",
}
PIN_FIELDS = {
    "name", "water_body", "water_body_id", "access_point", "latitude",
    "longitude", "spot_type", "primary_species", "confidence", "notes",
    "is_public",
}

FLOAT_FIELDS = {"air_temp", "water_temp", "length", "latitude", "longitude"}
INT_FIELDS = {"fish_count", "confidence"}
BOOL_FIELDS = {"kept", "is_public"}


def _coerce(field: str, value):
    if value in ("", None):
        return None
    if field in FLOAT_FIELDS:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if field in INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if field in BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("1", "true", "yes", "on", "kept")
    return value


def _assign(obj, data: dict, fields: set[str]):
    for field in fields:
        if field in data:
            setattr(obj, field, _coerce(field, data[field]))


def _touch(obj, data: dict):
    """Honor a client-supplied updated_at when syncing, else stamp now."""
    ts = data.get("updated_at")
    if ts:
        try:
            obj.updated_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return
        except (ValueError, AttributeError):
            pass
    obj.updated_at = datetime.now(timezone.utc)


def apply_trip(data: dict) -> tuple[Trip, bool]:
    trip = db.session.get(Trip, data["id"]) if data.get("id") else None
    created = trip is None
    if created:
        trip = Trip(id=data.get("id"))
        db.session.add(trip)
    _assign(trip, data, TRIP_FIELDS)
    return trip, created


def apply_catch(data: dict) -> tuple[Catch, bool]:
    catch = db.session.get(Catch, data["id"]) if data.get("id") else None
    created = catch is None
    if created:
        catch = Catch(id=data.get("id"))
        db.session.add(catch)
    _assign(catch, data, CATCH_FIELDS)
    return catch, created


def apply_pin(data: dict) -> tuple[MapPin, bool]:
    pin = db.session.get(MapPin, data["id"]) if data.get("id") else None
    created = pin is None
    if created:
        pin = MapPin(id=data.get("id"))
        db.session.add(pin)
    _assign(pin, data, PIN_FIELDS)
    return pin, created


# --- Trips ---------------------------------------------------------------------

@api_bp.get("/trips")
def list_trips():
    q = Trip.query
    species = request.args.get("species")
    water_body = request.args.get("water_body")
    bait = request.args.get("bait")
    weather = request.args.get("weather")
    keyword = request.args.get("q")
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    if water_body:
        q = q.filter(Trip.water_body.ilike(f"%{water_body}%"))
    if weather:
        q = q.filter(Trip.weather.ilike(f"%{weather}%"))
    if date_from:
        q = q.filter(Trip.date >= date_from)
    if date_to:
        q = q.filter(Trip.date <= date_to)

    trips = q.order_by(Trip.date.desc(), Trip.start_time.desc()).all()

    # Species / bait / keyword filters touch child catches, so filter in Python.
    def matches(t: Trip) -> bool:
        if species:
            s = species.lower()
            hit = s in (t.target_species or "").lower() or s in (t.species_caught or "").lower()
            hit = hit or any(s in (c.species or "").lower() for c in t.catches)
            if not hit:
                return False
        if bait:
            b = bait.lower()
            if not any(b in (c.bait or "").lower() for c in t.catches):
                return False
        if keyword:
            k = keyword.lower()
            blob = " ".join(filter(None, [
                t.notes, t.general_location, t.water_body, t.weather,
                t.hatch, t.species_caught, t.target_species,
            ])).lower()
            blob += " " + " ".join(
                filter(None, [(c.notes or "") + " " + (c.presentation or "") for c in t.catches])
            ).lower()
            if k not in blob:
                return False
        return True

    trips = [t for t in trips if matches(t)]
    return ok([t.to_dict() for t in trips])


@api_bp.get("/trips/<trip_id>")
def get_trip(trip_id):
    trip = db.session.get(Trip, trip_id)
    if not trip:
        return err("Trip not found", 404)
    return ok(trip.to_dict(include_children=True))


@api_bp.post("/trips")
def create_trip():
    data = request.get_json(silent=True) or {}
    if not data.get("date"):
        return err("date is required")
    trip, _ = apply_trip(data)
    db.session.commit()
    return ok(trip.to_dict(include_children=True), 201)


@api_bp.put("/trips/<trip_id>")
def update_trip(trip_id):
    data = request.get_json(silent=True) or {}
    data["id"] = trip_id
    if not db.session.get(Trip, trip_id):
        return err("Trip not found", 404)
    trip, _ = apply_trip(data)
    db.session.commit()
    return ok(trip.to_dict(include_children=True))


@api_bp.delete("/trips/<trip_id>")
def delete_trip(trip_id):
    trip = db.session.get(Trip, trip_id)
    if not trip:
        return err("Trip not found", 404)
    db.session.delete(trip)
    db.session.commit()
    return ok({"id": trip_id})


# --- Catches -------------------------------------------------------------------

@api_bp.get("/catches")
def list_catches():
    q = Catch.query
    species = request.args.get("species")
    bait = request.args.get("bait")
    trip_id = request.args.get("trip_id")
    pin_id = request.args.get("map_pin_id")
    if species:
        q = q.filter(Catch.species.ilike(f"%{species}%"))
    if bait:
        q = q.filter(Catch.bait.ilike(f"%{bait}%"))
    if trip_id:
        q = q.filter(Catch.trip_id == trip_id)
    if pin_id:
        q = q.filter(Catch.map_pin_id == pin_id)
    catches = q.order_by(Catch.created_at.desc()).all()
    return ok([c.to_dict() for c in catches])


@api_bp.post("/catches")
def create_catch():
    data = request.get_json(silent=True) or {}
    if not data.get("trip_id"):
        return err("trip_id is required")
    if not data.get("species"):
        return err("species is required")
    if not db.session.get(Trip, data["trip_id"]):
        return err("trip_id does not reference an existing trip", 404)
    catch, _ = apply_catch(data)
    db.session.commit()
    return ok(catch.to_dict(), 201)


@api_bp.put("/catches/<catch_id>")
def update_catch(catch_id):
    data = request.get_json(silent=True) or {}
    data["id"] = catch_id
    if not db.session.get(Catch, catch_id):
        return err("Catch not found", 404)
    catch, _ = apply_catch(data)
    db.session.commit()
    return ok(catch.to_dict())


@api_bp.delete("/catches/<catch_id>")
def delete_catch(catch_id):
    catch = db.session.get(Catch, catch_id)
    if not catch:
        return err("Catch not found", 404)
    db.session.delete(catch)
    db.session.commit()
    return ok({"id": catch_id})


# --- Map pins ------------------------------------------------------------------

@api_bp.get("/pins")
def list_pins():
    q = MapPin.query
    species = request.args.get("species")
    water_body = request.args.get("water_body")
    spot_type = request.args.get("spot_type")
    min_conf = request.args.get("min_confidence", type=int)
    if species:
        q = q.filter(MapPin.primary_species.ilike(f"%{species}%"))
    if water_body:
        q = q.filter(MapPin.water_body.ilike(f"%{water_body}%"))
    if spot_type:
        q = q.filter(MapPin.spot_type == spot_type)
    if min_conf:
        q = q.filter(MapPin.confidence >= min_conf)
    pins = q.order_by(MapPin.confidence.desc(), MapPin.name).all()
    return ok([p.to_dict() for p in pins])


@api_bp.post("/pins")
def create_pin():
    data = request.get_json(silent=True) or {}
    if data.get("latitude") in (None, "") or data.get("longitude") in (None, ""):
        return err("latitude and longitude are required")
    if not data.get("name"):
        return err("name is required")
    pin, _ = apply_pin(data)
    db.session.commit()
    return ok(pin.to_dict(), 201)


@api_bp.put("/pins/<pin_id>")
def update_pin(pin_id):
    data = request.get_json(silent=True) or {}
    data["id"] = pin_id
    if not db.session.get(MapPin, pin_id):
        return err("Pin not found", 404)
    pin, _ = apply_pin(data)
    db.session.commit()
    return ok(pin.to_dict())


@api_bp.delete("/pins/<pin_id>")
def delete_pin(pin_id):
    pin = db.session.get(MapPin, pin_id)
    if not pin:
        return err("Pin not found", 404)
    db.session.delete(pin)
    db.session.commit()
    return ok({"id": pin_id})
