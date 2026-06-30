#!/usr/bin/env bash
set -e

# Tables are created automatically by the app factory (db.create_all).
# Optionally load the East Tennessee sample data on first boot.
#   AUTO_SEED=1  -> seed only if the database has no trips yet
#   AUTO_SEED=force -> always reseed (wipes seeded tables)
if [ "${AUTO_SEED:-0}" != "0" ]; then
  python - <<'PY'
import os
from app import create_app
from app.models import Trip
from prisma.seed import seed

app = create_app()
with app.app_context():
    mode = os.environ.get("AUTO_SEED", "0")
    if mode == "force" or Trip.query.count() == 0:
        seed()
    else:
        print(f"AUTO_SEED: database already has {Trip.query.count()} trips; skipping seed.")
PY
fi

exec "$@"
