"""SQLAlchemy models for Fishing Atlas.

Design notes
------------
* **String UUID primary keys.** Records can be created on the phone while
  offline; the client generates the UUID so the id is stable before and after
  it syncs to the server. No id-remapping is needed on sync.
* **String dates/times.** ``date`` is ``YYYY-MM-DD`` and times are ``HH:MM``.
  Storing them as strings keeps JSON sync payloads loss-free and avoids
  timezone/parse surprises between the phone and the server. Aggregations
  (best month, best time of day) are done in Python over a personal-scale
  dataset.
* **updated_at** drives last-write-wins conflict detection during sync.
* Water body / access point are stored both as a free-text name (fast,
  offline-friendly entry) and an optional FK to the catalog tables, which power
  autocomplete and seed data.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .extensions import db


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=_now, onupdate=_now, nullable=False)

    @staticmethod
    def _iso(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None


class WaterBody(TimestampMixin, db.Model):
    __tablename__ = "water_bodies"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(160), nullable=False, unique=True)
    kind = db.Column(db.String(40))  # river, creek, tailwater, pond, lake, ...
    region = db.Column(db.String(160))
    notes = db.Column(db.Text)

    access_points = db.relationship(
        "AccessPoint", back_populates="water_body", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "region": self.region,
            "notes": self.notes,
        }


class AccessPoint(TimestampMixin, db.Model):
    __tablename__ = "access_points"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(160), nullable=False)
    water_body_id = db.Column(db.String(36), db.ForeignKey("water_bodies.id"))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    notes = db.Column(db.Text)

    water_body = db.relationship("WaterBody", back_populates="access_points")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "water_body_id": self.water_body_id,
            "water_body": self.water_body.name if self.water_body else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "notes": self.notes,
        }


class Trip(TimestampMixin, db.Model):
    __tablename__ = "trips"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)

    # Core
    date = db.Column(db.String(10), nullable=False, index=True)  # YYYY-MM-DD
    start_time = db.Column(db.String(5))  # HH:MM
    end_time = db.Column(db.String(5))
    water_body = db.Column(db.String(160), index=True)
    water_body_id = db.Column(db.String(36), db.ForeignKey("water_bodies.id"))
    access_point = db.Column(db.String(160))
    general_location = db.Column(db.String(240))
    # One or more of FISHING_TYPES, stored comma-separated (e.g. "fly,tenkara").
    # Kept as a plain string so the offline sync engine treats it like any other
    # field; a single value (legacy data) is a valid one-item list.
    fishing_type = db.Column(db.String(120))
    target_species = db.Column(db.String(240))
    species_caught = db.Column(db.String(240))
    fish_count = db.Column(db.Integer, default=0)
    largest_fish = db.Column(db.String(120))
    notes = db.Column(db.Text)

    # Conditions (logged per trip)
    air_temp = db.Column(db.Float)
    water_temp = db.Column(db.Float)
    weather = db.Column(db.String(120))
    cloud_cover = db.Column(db.String(80))
    wind = db.Column(db.String(120))
    water_clarity = db.Column(db.String(80))  # clear, stained, muddy, ...
    water_level = db.Column(db.String(80))  # low, normal, high, ...
    flow = db.Column(db.String(80))  # CFS or description, optional
    recent_rain = db.Column(db.String(120))
    moon_phase = db.Column(db.String(80))
    hatch = db.Column(db.String(240))  # visible insect activity, optional

    catches = db.relationship(
        "Catch", back_populates="trip", cascade="all, delete-orphan"
    )
    photos = db.relationship(
        "Photo", back_populates="trip", cascade="all, delete-orphan"
    )

    @property
    def computed_fish_count(self) -> int:
        return self.fish_count if self.fish_count else len(self.catches)

    def to_dict(self, include_children: bool = False) -> dict:
        data = {
            "id": self.id,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "water_body": self.water_body,
            "water_body_id": self.water_body_id,
            "access_point": self.access_point,
            "general_location": self.general_location,
            "fishing_type": self.fishing_type,
            "target_species": self.target_species,
            "species_caught": self.species_caught,
            "fish_count": self.fish_count,
            "largest_fish": self.largest_fish,
            "notes": self.notes,
            "air_temp": self.air_temp,
            "water_temp": self.water_temp,
            "weather": self.weather,
            "cloud_cover": self.cloud_cover,
            "wind": self.wind,
            "water_clarity": self.water_clarity,
            "water_level": self.water_level,
            "flow": self.flow,
            "recent_rain": self.recent_rain,
            "moon_phase": self.moon_phase,
            "hatch": self.hatch,
            "updated_at": self._iso(self.updated_at),
            "created_at": self._iso(self.created_at),
        }
        if include_children:
            data["catches"] = [c.to_dict() for c in self.catches]
            data["photos"] = [p.to_dict() for p in self.photos]
        return data


class MapPin(TimestampMixin, db.Model):
    __tablename__ = "map_pins"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(160), nullable=False)
    water_body = db.Column(db.String(160), index=True)
    water_body_id = db.Column(db.String(36), db.ForeignKey("water_bodies.id"))
    access_point = db.Column(db.String(160))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    # riffle, pool, run, pocket water, laydown, undercut bank, gravel bar,
    # bridge, dam, tailwater, pond, lake, other
    spot_type = db.Column(db.String(60))
    primary_species = db.Column(db.String(160))
    confidence = db.Column(db.Integer, default=3)  # 1..5
    notes = db.Column(db.Text)
    is_public = db.Column(db.Boolean, default=False, nullable=False)

    catches = db.relationship("Catch", back_populates="map_pin")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "water_body": self.water_body,
            "water_body_id": self.water_body_id,
            "access_point": self.access_point,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "spot_type": self.spot_type,
            "primary_species": self.primary_species,
            "confidence": self.confidence,
            "notes": self.notes,
            "is_public": self.is_public,
            "catch_count": len(self.catches),
            "updated_at": self._iso(self.updated_at),
            "created_at": self._iso(self.created_at),
        }


class Catch(TimestampMixin, db.Model):
    __tablename__ = "catches"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    trip_id = db.Column(db.String(36), db.ForeignKey("trips.id"), nullable=False, index=True)
    map_pin_id = db.Column(db.String(36), db.ForeignKey("map_pins.id"), index=True)

    species = db.Column(db.String(120), nullable=False, index=True)
    length = db.Column(db.Float)  # estimated length (inches)
    time_caught = db.Column(db.String(5))  # HH:MM
    bait = db.Column(db.String(160))  # fly, lure, or bait used
    presentation = db.Column(db.Text)  # presentation notes
    water_type = db.Column(db.String(120))  # depth or water type
    kept = db.Column(db.Boolean, default=False)  # True=kept, False=released
    notes = db.Column(db.Text)

    trip = db.relationship("Trip", back_populates="catches")
    map_pin = db.relationship("MapPin", back_populates="catches")
    photos = db.relationship(
        "Photo", back_populates="catch", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "map_pin_id": self.map_pin_id,
            "species": self.species,
            "length": self.length,
            "time_caught": self.time_caught,
            "bait": self.bait,
            "presentation": self.presentation,
            "water_type": self.water_type,
            "kept": self.kept,
            "notes": self.notes,
            "photos": [p.to_dict() for p in self.photos],
            "updated_at": self._iso(self.updated_at),
            "created_at": self._iso(self.created_at),
        }


class Photo(TimestampMixin, db.Model):
    __tablename__ = "photos"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    trip_id = db.Column(db.String(36), db.ForeignKey("trips.id"), index=True)
    catch_id = db.Column(db.String(36), db.ForeignKey("catches.id"), index=True)
    filename = db.Column(db.String(255))  # stored file in UPLOAD_FOLDER
    url = db.Column(db.String(512))  # public URL/path to serve
    caption = db.Column(db.String(240))

    trip = db.relationship("Trip", back_populates="photos")
    catch = db.relationship("Catch", back_populates="photos")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "catch_id": self.catch_id,
            "filename": self.filename,
            "url": self.url,
            "caption": self.caption,
        }


class GearItem(TimestampMixin, db.Model):
    """Optional gear/fly/lure catalog — powers autocomplete and the dashboard."""

    __tablename__ = "gear_items"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    name = db.Column(db.String(160), nullable=False, unique=True)
    kind = db.Column(db.String(40))  # fly, lure, bait, rod, other
    notes = db.Column(db.Text)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "kind": self.kind, "notes": self.notes}
