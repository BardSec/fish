"""Dashboard aggregations and catalog/lookup endpoints.

Aggregations run in Python over the full dataset. This is intentional: a
personal fishing journal is small (hundreds, not millions, of rows), and Python
keeps the season/time-of-day bucketing logic readable and DB-agnostic.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from . import api_bp, ok
from ..constants import (
    CLOUD_COVER, COMMON_SPECIES, FISHING_TYPES, MOON_PHASES, SPOT_TYPES,
    WATER_CLARITY, WATER_LEVELS, season_for_month,
)
from ..models import AccessPoint, Catch, GearItem, MapPin, Trip, WaterBody


def _month_name(date_str: str) -> str | None:
    # date_str is YYYY-MM-DD
    try:
        month = int(date_str[5:7])
    except (ValueError, IndexError):
        return None
    return [
        "January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December",
    ][month - 1]


def _time_bucket(hhmm: str | None) -> str | None:
    if not hhmm:
        return None
    try:
        hour = int(hhmm[:2])
    except (ValueError, IndexError):
        return None
    if 4 <= hour < 8:
        return "Early morning (4–8am)"
    if 8 <= hour < 11:
        return "Morning (8–11am)"
    if 11 <= hour < 14:
        return "Midday (11am–2pm)"
    if 14 <= hour < 17:
        return "Afternoon (2–5pm)"
    if 17 <= hour < 21:
        return "Evening (5–9pm)"
    return "Night (9pm–4am)"


def _ranked(counter: Counter, limit: int = 5):
    return [{"label": k, "count": v} for k, v in counter.most_common(limit)]


@api_bp.get("/dashboard")
def dashboard():
    trips = Trip.query.all()
    catches = Catch.query.all()
    pins = MapPin.query.all()

    species = Counter()
    baits = Counter()
    months = Counter()
    seasons = Counter()
    times = Counter()
    water_bodies = Counter()

    total_fish = 0
    for t in trips:
        # A trip's fish tally: explicit count if given, else number of catches.
        n = t.fish_count if t.fish_count else len(t.catches)
        total_fish += n
        if t.water_body:
            water_bodies[t.water_body] += n
        mname = _month_name(t.date)
        if mname:
            months[mname] += n
        try:
            seasons[season_for_month(int(t.date[5:7]))] += n
        except (ValueError, IndexError):
            pass

    for c in catches:
        if c.species:
            species[c.species] += 1
        if c.bait:
            baits[c.bait] += 1
        bucket = _time_bucket(c.time_caught)
        if bucket:
            times[bucket] += 1

    pin_productivity = sorted(
        pins, key=lambda p: (len(p.catches), p.confidence or 0), reverse=True
    )

    recent = sorted(
        trips, key=lambda t: (t.date or "", t.start_time or ""), reverse=True
    )[:6]

    return ok({
        "total_trips": len(trips),
        "total_fish": total_fish,
        "total_pins": len(pins),
        "total_catches": len(catches),
        "top_species": _ranked(species),
        "best_water_bodies": _ranked(water_bodies),
        "best_baits": _ranked(baits),
        "best_months": _ranked(months),
        "best_seasons": _ranked(seasons),
        "best_time_of_day": _ranked(times),
        "recent_trips": [t.to_dict() for t in recent],
        "most_productive_pins": [
            {**p.to_dict(), "catch_count": len(p.catches)}
            for p in pin_productivity[:6]
        ],
    })


@api_bp.get("/meta")
def meta():
    """Catalog data + choice lists for forms and autocomplete."""
    # Distinct values already in use, merged with seed catalogs.
    used_baits = {c.bait for c in Catch.query.all() if c.bait}
    used_species = {c.species for c in Catch.query.all() if c.species}
    gear = [g.to_dict() for g in GearItem.query.order_by(GearItem.name).all()]

    return ok({
        "water_bodies": [w.name for w in WaterBody.query.order_by(WaterBody.name).all()],
        "access_points": [a.to_dict() for a in
                          AccessPoint.query.order_by(AccessPoint.name).all()],
        "gear": gear,
        "species": sorted(set(COMMON_SPECIES) | used_species),
        "baits": sorted({g["name"] for g in gear} | used_baits),
        "choices": {
            "fishing_types": FISHING_TYPES,
            "spot_types": SPOT_TYPES,
            "water_clarity": WATER_CLARITY,
            "water_levels": WATER_LEVELS,
            "cloud_cover": CLOUD_COVER,
            "moon_phases": MOON_PHASES,
        },
    })
