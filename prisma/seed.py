"""Seed the database with East Tennessee fishing data.

Run with::

    python -m prisma.seed          # or: flask --app wsgi seed  (see README)

Re-running is safe: it wipes the seeded tables and recreates them so you always
get a clean, known dataset. (Named ``prisma/seed.py`` to mirror the original
spec's layout, even though we use SQLAlchemy rather than Prisma.)
"""
import sys
from pathlib import Path

# Allow running as a plain script (python prisma/seed.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (  # noqa: E402
    AccessPoint, Catch, GearItem, MapPin, Photo, Trip, WaterBody,
)

WATER_BODIES = [
    ("Little River", "freestone river", "Blount County, East TN"),
    ("Abrams Creek", "creek", "Great Smoky Mountains NP"),
    ("Pistol Creek", "creek", "Maryville, TN"),
]

# (name, water_body_name, lat, lng, notes)
ACCESS_POINTS = [
    ("Townsend \"Y\"", "Little River", 35.6754, -83.7563, "Confluence at the park boundary; easy wade access."),
    ("Peery's Mill", "Little River", 35.6660, -83.7090, "Deep pools below the old mill site near Walland."),
    ("Metcalf Bottoms", "Little River", 35.6826, -83.6300, "Picnic area; pocket water and runs upstream."),
    ("Abrams Creek Campground", "Abrams Creek", 35.6093, -83.9343, "Lower Abrams near Chilhowee Lake."),
    ("Maryville Water Filtration Plant", "Little River", 35.7480, -83.9450, "Public access stretch near the plant."),
    ("Pistol Creek Greenway", "Pistol Creek", 35.7565, -83.9705, "Urban greenway; panfish and rock bass."),
]

GEAR = [
    ("Parachute Adams", "fly"), ("Elk Hair Caddis", "fly"), ("Pheasant Tail Nymph", "fly"),
    ("Tellico Nymph", "fly"), ("Wooly Bugger", "fly"), ("Tenkara Kebari", "fly"),
    ("Clouser Minnow", "fly"), ("Ned Rig", "lure"), ("Rooster Tail Spinner", "lure"),
    ("Crawfish Crankbait", "lure"), ("Nightcrawler", "bait"),
]

# Pins: (name, wb, access, lat, lng, spot_type, species, confidence, notes, public)
PINS = [
    ("Townsend Y Riffle", "Little River", "Townsend \"Y\"", 35.6756, -83.7569,
     "riffle", "Rainbow trout", 4, "Stocked rainbows hold in the seam; caddis in spring.", False),
    ("Peery's Mill Pool", "Little River", "Peery's Mill", 35.6662, -83.7092,
     "pool", "Smallmouth bass", 5, "Big slow pool — best smallmouth water in summer.", False),
    ("Metcalf Bottoms Run", "Little River", "Metcalf Bottoms", 35.6828, -83.6305,
     "run", "Brown trout", 3, "Wild browns hold tight to the bank under the laurel.", False),
    ("Abrams Ledge", "Abrams Creek", "Abrams Creek Campground", 35.6098, -83.9351,
     "pocket water", "Rock bass", 4, "Rock bass and redeye stacked behind the ledge.", False),
    ("Filtration Plant Gravel Bar", "Little River", "Maryville Water Filtration Plant", 35.7482, -83.9455,
     "gravel bar", "Smallmouth bass", 4, "Wade the gravel bar at normal flow; crawfish patterns.", False),
    ("Pistol Creek Bridge", "Pistol Creek", "Pistol Creek Greenway", 35.7567, -83.9708,
     "bridge", "Bluegill", 3, "Panfish under the footbridge — great for quick after-work trips.", True),
]


def reset():
    for model in (Photo, Catch, MapPin, AccessPoint, WaterBody, GearItem, Trip):
        model.query.delete()
    db.session.commit()


def seed():
    reset()

    wb_by_name = {}
    for name, kind, region in WATER_BODIES:
        wb = WaterBody(name=name, kind=kind, region=region)
        db.session.add(wb)
        wb_by_name[name] = wb
    db.session.flush()

    for name, wb_name, lat, lng, notes in ACCESS_POINTS:
        db.session.add(AccessPoint(
            name=name, water_body=wb_by_name[wb_name], latitude=lat, longitude=lng, notes=notes))

    for name, kind in GEAR:
        db.session.add(GearItem(name=name, kind=kind))

    pin_by_name = {}
    for name, wb, ap, lat, lng, spot, sp, conf, notes, pub in PINS:
        pin = MapPin(
            name=name, water_body=wb, water_body_id=wb_by_name[wb].id, access_point=ap,
            latitude=lat, longitude=lng, spot_type=spot, primary_species=sp,
            confidence=conf, notes=notes, is_public=pub)
        db.session.add(pin)
        pin_by_name[name] = pin
    db.session.flush()

    # --- Trips with catches ---------------------------------------------------
    trips = []

    t1 = Trip(
        date="2026-04-18", start_time="07:30", end_time="11:00",
        water_body="Little River", water_body_id=wb_by_name["Little River"].id,
        access_point="Townsend \"Y\"", general_location="From the Y up to the swimming hole",
        fishing_type="fly", target_species="Rainbow trout, Brown trout",
        species_caught="Rainbow trout, Brown trout", fish_count=6, largest_fish="12\" rainbow",
        notes="Strong caddis hatch mid-morning. Fish keyed on emergers in the riffles.",
        air_temp=58, water_temp=52, weather="partly sunny", cloud_cover="partly cloudy",
        wind="light, 3-5 mph", water_clarity="clear", water_level="normal",
        flow="210 CFS", recent_rain="trace overnight", moon_phase="waxing gibbous",
        hatch="caddis (size 16)")
    db.session.add(t1)
    db.session.flush()
    db.session.add_all([
        Catch(trip_id=t1.id, map_pin_id=pin_by_name["Townsend Y Riffle"].id,
              species="Rainbow trout", length=12, time_caught="09:15", bait="Elk Hair Caddis",
              presentation="Dead drift through the riffle seam", water_type="riffle, 2ft",
              kept=False, notes="Best fish of the day."),
        Catch(trip_id=t1.id, map_pin_id=pin_by_name["Townsend Y Riffle"].id,
              species="Rainbow trout", length=9, time_caught="09:40", bait="Pheasant Tail Nymph",
              presentation="Dropper under the caddis", water_type="riffle", kept=False),
        Catch(trip_id=t1.id, species="Brown trout", length=10, time_caught="10:20",
              bait="Parachute Adams", presentation="Tight to the bank", water_type="run", kept=False),
    ])
    trips.append(t1)

    t2 = Trip(
        date="2026-05-30", start_time="08:00", end_time="12:30",
        water_body="Abrams Creek", water_body_id=wb_by_name["Abrams Creek"].id,
        access_point="Abrams Creek Campground", general_location="Lower Abrams above the lake",
        fishing_type="tenkara", target_species="Rock bass, Rainbow trout",
        species_caught="Rock bass, Redbreast sunfish", fish_count=8, largest_fish="9\" rock bass",
        notes="Pocket water fished great with a single kebari. Lots of aggressive rock bass.",
        air_temp=72, water_temp=64, weather="overcast", cloud_cover="overcast",
        wind="calm", water_clarity="slightly stained", water_level="normal",
        recent_rain="0.3in two days ago", hatch="some yellow sallies")
    db.session.add(t2)
    db.session.flush()
    db.session.add_all([
        Catch(trip_id=t2.id, map_pin_id=pin_by_name["Abrams Ledge"].id,
              species="Rock bass", length=9, time_caught="09:05", bait="Tenkara Kebari",
              presentation="Swung through pocket", water_type="pocket water", kept=False),
        Catch(trip_id=t2.id, map_pin_id=pin_by_name["Abrams Ledge"].id,
              species="Redbreast sunfish", length=6, time_caught="10:10", bait="Tenkara Kebari",
              water_type="pool tailout", kept=False),
    ])
    trips.append(t2)

    t3 = Trip(
        date="2026-06-15", start_time="17:30", end_time="20:30",
        water_body="Little River", water_body_id=wb_by_name["Little River"].id,
        access_point="Peery's Mill", general_location="The big pool below the mill",
        fishing_type="spin", target_species="Smallmouth bass",
        species_caught="Smallmouth bass, Rock bass", fish_count=11, largest_fish="15\" smallmouth",
        notes="Evening smallmouth bite turned on at dusk. Ned rig along the ledge.",
        air_temp=84, water_temp=74, weather="clear and hot", cloud_cover="clear",
        wind="light SW", water_clarity="clear", water_level="low",
        flow="120 CFS", moon_phase="new", hatch="none noted")
    db.session.add(t3)
    db.session.flush()
    db.session.add_all([
        Catch(trip_id=t3.id, map_pin_id=pin_by_name["Peery's Mill Pool"].id,
              species="Smallmouth bass", length=15, time_caught="19:50", bait="Ned Rig",
              presentation="Slow drag down the ledge", water_type="pool, 6ft", kept=False,
              notes="Hammered it on the fall."),
        Catch(trip_id=t3.id, map_pin_id=pin_by_name["Peery's Mill Pool"].id,
              species="Smallmouth bass", length=12, time_caught="20:05", bait="Ned Rig",
              water_type="pool", kept=False),
        Catch(trip_id=t3.id, species="Rock bass", length=7, time_caught="18:40",
              bait="Rooster Tail Spinner", water_type="run", kept=False),
    ])
    trips.append(t3)

    t4 = Trip(
        date="2026-06-25", start_time="18:00", end_time="19:45",
        water_body="Pistol Creek", water_body_id=wb_by_name["Pistol Creek"].id,
        access_point="Pistol Creek Greenway", general_location="Footbridge pool on the greenway",
        fishing_type="bank", target_species="Bluegill, Redbreast sunfish",
        species_caught="Bluegill, Redbreast sunfish, Rock bass", fish_count=14, largest_fish="8\" bluegill",
        notes="Quick after-work panfish session with the kids. Nonstop action on worms.",
        air_temp=81, water_temp=76, weather="hazy sun", cloud_cover="partly cloudy",
        wind="calm", water_clarity="stained", water_level="normal", recent_rain="none")
    db.session.add(t4)
    db.session.flush()
    db.session.add_all([
        Catch(trip_id=t4.id, map_pin_id=pin_by_name["Pistol Creek Bridge"].id,
              species="Bluegill", length=8, time_caught="18:20", bait="Nightcrawler",
              water_type="pool, 3ft", kept=False),
        Catch(trip_id=t4.id, map_pin_id=pin_by_name["Pistol Creek Bridge"].id,
              species="Redbreast sunfish", length=6, time_caught="18:45", bait="Nightcrawler",
              water_type="undercut bank", kept=False),
        Catch(trip_id=t4.id, species="Rock bass", length=7, time_caught="19:10",
              bait="Nightcrawler", water_type="laydown", kept=True, notes="Kept a couple for the pan."),
    ])
    trips.append(t4)

    db.session.commit()
    print(f"Seeded {WaterBody.query.count()} water bodies, "
          f"{AccessPoint.query.count()} access points, {GearItem.query.count()} gear items, "
          f"{MapPin.query.count()} pins, {Trip.query.count()} trips, {Catch.query.count()} catches.")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        seed()
