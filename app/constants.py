"""Shared choice lists used by forms, the API, and seed data."""

FISHING_TYPES = ["fly", "spin", "tenkara", "bait", "kayak", "wade", "bank"]

SPOT_TYPES = [
    "riffle",
    "pool",
    "run",
    "pocket water",
    "laydown",
    "undercut bank",
    "gravel bar",
    "bridge",
    "dam",
    "tailwater",
    "pond",
    "lake",
    "other",
]

WATER_CLARITY = ["clear", "slightly stained", "stained", "muddy"]
WATER_LEVELS = ["very low", "low", "normal", "high", "very high", "flood"]
CLOUD_COVER = ["clear", "partly cloudy", "mostly cloudy", "overcast"]
MOON_PHASES = [
    "new",
    "waxing crescent",
    "first quarter",
    "waxing gibbous",
    "full",
    "waning gibbous",
    "last quarter",
    "waning crescent",
]

COMMON_SPECIES = [
    "Smallmouth bass",
    "Rock bass",
    "Redbreast sunfish",
    "Bluegill",
    "Rainbow trout",
    "Brown trout",
    "Brook trout",
    "Largemouth bass",
]

SEASONS = {
    "Winter": (12, 1, 2),
    "Spring": (3, 4, 5),
    "Summer": (6, 7, 8),
    "Fall": (9, 10, 11),
}


def season_for_month(month: int) -> str:
    for name, months in SEASONS.items():
        if month in months:
            return name
    return "Unknown"
