# 🎣 Fishing Atlas

A personal fishing journal and map-based atlas. Log trips, conditions, and
catches; pin productive spots on a map; and watch patterns emerge over time —
by location, species, season, water level, weather, fly/lure, and time of day.

Built **mobile-first** and **offline-first**: install it to your phone's home
screen and keep logging even with no cell signal. Everything you enter is saved
on the device immediately and **syncs automatically when you're back online**.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | **Flask** (app factory + blueprints) |
| ORM / migrations | **SQLAlchemy** + **Flask-Migrate** (Alembic) |
| Database | **SQLite** (single file; Docker volume) |
| Frontend | Server-rendered **Jinja2** + vanilla JS (no build step) |
| Map | **Leaflet + OpenStreetMap** (no API key required) |
| Offline | **PWA** — web manifest, service worker, IndexedDB, sync queue |
| Deploy | **Docker** + docker-compose, served by **gunicorn** |

> **Note on the original spec.** The brief asked for a Prisma schema and Mapbox.
> This project targets a Flask/Docker stack, so:
> - **Prisma → SQLAlchemy.** Prisma is JS-native and awkward in Python. The
>   models in `app/models.py` map 1:1 to the requested entities (Trip, Catch,
>   MapPin, Photo, WaterBody, AccessPoint, GearItem). The seed script lives at
>   `prisma/seed.py` to mirror the requested layout.
> - **Mapbox → Leaflet/OpenStreetMap.** Leaflet needs **no API key**, so there's
>   nothing secret to put in `.env` for the map. All config is still read from
>   the environment (see `.env.example`); if you later switch to a token-based
>   tile provider, set `MAP_TILE_URL` there and the key never touches source.

---

## Quick start

### Option A — Docker (recommended)

```bash
cp .env.example .env          # optional: edit SECRET_KEY etc.
docker compose up --build
```

Open <http://localhost:5000>. On first boot the database is created and the
East Tennessee sample data is loaded automatically (`AUTO_SEED=1`). Data
persists in named volumes (`atlas-data` for the SQLite file, `atlas-uploads`
for photos).

To wipe and reload the sample data: `AUTO_SEED=force docker compose up --build`.

### Option B — Local Python

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python prisma/seed.py          # create tables + load sample data
python wsgi.py                 # dev server at http://127.0.0.1:5000
```

(`flask --app wsgi seed` does the same seeding via the CLI. For production-style
serving: `gunicorn wsgi:app`.)

---

## Pages

| Path | Page |
|---|---|
| `/` | **Dashboard** — totals, top species, best water bodies/flies/months/seasons/time-of-day, recent trips, most productive pins |
| `/trips` | **Trips** list with search + filters |
| `/trips/new` | **New Trip** form (trip details + full conditions + photos) |
| `/trips/<id>` | **Trip Detail** + inline **catch logging** |
| `/catches` | All **Catches** with filters |
| `/map` | **Map Atlas** — drop/edit pins, filter, "use my location" |
| `/pins` | **Pins** list with filters |
| `/settings` | Theme, sync status & controls, conflict resolution, JSON export |
| `/offline` | Offline fallback page |

---

## Data model

`app/models.py` — string **UUID** primary keys (so the phone can create records
offline and sync them without id-remapping) and `updated_at` timestamps (used
for conflict detection).

- **Trip** — date, times, water body, access point, location, fishing type,
  target/caught species, counts, largest fish, notes, **plus all conditions**
  (air/water temp, weather, cloud cover, wind, clarity, level, flow, recent
  rain, moon phase, hatch). Has many **Catch** and many **Photo**.
- **Catch** — belongs to a Trip, optionally to a **MapPin**; species, length,
  time, fly/lure/bait, presentation, depth/water type, kept/released, notes,
  photos.
- **MapPin** — name, water body, access point, lat/lng, spot type, primary
  species, confidence (1–5), notes, public/private (default private). Has many
  Catch over time.
- **Photo** — linked to a Trip and/or Catch; stored on disk, served from
  `/static/uploads`.
- **WaterBody**, **AccessPoint** — catalog tables powering autocomplete + seed
  data. **GearItem** — optional fly/lure/bait catalog.

Dashboard aggregations run in Python (personal-scale data) in
`app/api/dashboard.py`.

---

## REST API

All mutations go through the JSON API (used by both the live UI and the offline
sync engine). Responses are `{ "ok": true, "data": ... }`.

```
GET    /api/dashboard
GET    /api/meta                       # choice lists + autocomplete catalogs
GET    /api/trips        ?species&water_body&bait&weather&q&from&to
POST   /api/trips        PUT/DELETE /api/trips/<id>
GET    /api/trips/<id>                 # includes catches + photos
GET    /api/catches      ?species&bait&trip_id&map_pin_id
POST   /api/catches      PUT/DELETE /api/catches/<id>
GET    /api/pins         ?species&water_body&spot_type&min_confidence
POST   /api/pins         PUT/DELETE /api/pins/<id>
POST   /api/photos                     # multipart 'file' OR JSON {data_url}
POST   /api/sync                       # batch upsert/delete from the offline queue
GET    /api/sync/snapshot              # full dataset for local caching / export
```

---

## Offline-first behavior

The app is an installable PWA. The key idea: **the phone is the source of truth
while offline, and the server reconciles on reconnect.**

**What works with no signal**
- Open the core pages (dashboard, trips, new trip, catches, map, pins,
  settings) — cached by the service worker (`app/static/sw.js`).
- Start a trip, log catches, add notes, and create map pins. Each write goes
  to **IndexedDB** first (`app/static/js/db.js`) and is appended to a **sync
  queue**.
- Browse map areas you've already viewed — map tiles are runtime-cached.
- A header badge shows live status: **Synced / N to sync / Offline · N queued /
  Syncing**.

**What happens on reconnect** (`app/static/js/sync.js`)
1. The queue is POSTed to `/api/sync` as a batch.
2. The server upserts each record by UUID and returns the canonical version,
   which the client adopts.
3. Queued photos upload to `/api/photos`.
4. A fresh snapshot is pulled so the local mirror matches the server.

**Conflict handling** (last-write-wins, kept deliberately simple):
- Each queued edit carries `base_updated_at` (the version it was based on). If
  the server's record changed since then, it's a **conflict**, resolved by
  comparing timestamps:
  - **client newer** → applied (`conflict_client_wins`);
  - **server newer** → the offline edit is dropped, the server version adopted,
    and the conflict is recorded for review (`conflict_server_wins`).
- Review/resolve conflicts on the **Settings** page ("Keep server version" /
  "Re-apply my edit").

### Limitations (by design — reliability over cleverness)
- **Last-write-wins**, not field-level merge. Two devices editing the *same*
  record while both offline: the later write wins; the loser is surfaced as a
  conflict rather than auto-merged.
- Intended for a **single user** (no auth/multi-tenant). The public/private pin
  toggle is stored but there's no separate public sharing surface.
- **Offline reads** show locally-created records plus the last synced snapshot;
  server-side filtering falls back to simpler client-side filtering when
  offline.
- Photos captured offline are queued as data URLs and uploaded on reconnect;
  very large photo backlogs are bounded by device storage.
- Map **tiles** require a connection the first time you view an area (they're
  cached afterward). The map UI itself (Leaflet) is vendored locally and works
  offline.

---

## Project structure

```
fish/
├── app/
│   ├── __init__.py            # app factory, blueprints, CLI
│   ├── extensions.py          # db, migrate
│   ├── models.py              # SQLAlchemy models
│   ├── constants.py           # shared choice lists
│   ├── views.py               # page routes + PWA asset routes
│   ├── api/                   # JSON API (resources, dashboard, sync, photos)
│   ├── templates/             # Jinja2 pages (base + 9 pages + offline)
│   └── static/
│       ├── css/styles.css     # mobile-first dark/light styling
│       ├── js/                # db, api, sync, app + one file per page
│       ├── vendor/leaflet/    # Leaflet vendored for offline use
│       ├── icons/             # generated PWA icons
│       ├── manifest.webmanifest
│       └── sw.js              # service worker
├── prisma/seed.py             # East TN seed data (SQLAlchemy)
├── config.py                  # env-driven config
├── wsgi.py                    # entry point
├── requirements.txt
├── Dockerfile / docker-entrypoint.sh / docker-compose.yml
└── .env.example
```

---

## Sample data

`prisma/seed.py` loads East Tennessee locations — **Little River** (Townsend
"Y", Peery's Mill, Metcalf Bottoms), **Abrams Creek**, **Pistol Creek**
(Maryville greenway), and a **Maryville Water Filtration Plant** access point —
with six map pins and four sample trips (smallmouth/rock bass/redbreast/bluegill
plus rainbow/brown trout) on flies, Ned rigs, tenkara, and nightcrawlers.

## Database migrations

Tables are auto-created on first boot for a friction-free start. For schema
changes over time, use Flask-Migrate:

```bash
flask --app wsgi db init       # once
flask --app wsgi db migrate -m "describe change"
flask --app wsgi db upgrade
```

## Tests

`tests/test_api.py` covers the API, dashboard, filters, photo upload, and the
sync/conflict paths against an in-memory database:

```bash
pip install pytest
pytest
```

## Assumptions

- Single personal user; no authentication.
- Temperatures in °F, lengths in inches (free-text where helpful).
- Dates/times stored as strings (`YYYY-MM-DD`, `HH:MM`) for loss-free offline
  sync; aggregations done in Python.
- "Fish count" uses the trip's explicit count, falling back to the number of
  logged catches.
