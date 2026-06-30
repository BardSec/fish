"""Offline sync engine endpoints.

The phone keeps its own copy of records in IndexedDB and a queue of pending
mutations. When connectivity returns it POSTs the queue to ``/api/sync``.

Conflict strategy (deliberately simple & reliable — see README):

* Each queued mutation carries ``base_updated_at`` — the server timestamp the
  edit was based on — and ``data.updated_at`` — when the edit happened on the
  device.
* If the server's current ``updated_at`` is **newer** than ``base_updated_at``,
  another write landed in between → **conflict**. We resolve last-write-wins by
  comparing timestamps and report the outcome so the client can surface it:
    - ``conflict_client_wins`` — the offline edit was newer; it was applied.
    - ``conflict_server_wins`` — the server copy was newer; offline edit dropped,
      the server record is returned so the client can adopt it.
* No conflict → ``applied``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from . import api_bp, err, ok
from ..extensions import db
from ..models import Catch, MapPin, Trip
from .resources import apply_catch, apply_pin, apply_trip

_APPLIERS = {"trip": apply_trip, "catch": apply_catch, "pin": apply_pin}
_MODELS = {"trip": Trip, "catch": Catch, "pin": MapPin}


def _naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return _naive(datetime.fromisoformat(s.replace("Z", "+00:00")))
    except (ValueError, AttributeError):
        return None


@api_bp.post("/sync")
def sync():
    payload = request.get_json(silent=True) or {}
    operations = payload.get("operations", [])
    results = []

    for op in operations:
        entity = op.get("entity")
        op_id = op.get("id")
        kind = op.get("op", "upsert")
        client_op_id = op.get("op_id")  # client's queue id, echoed back

        if entity not in _APPLIERS:
            results.append({"op_id": client_op_id, "id": op_id,
                            "status": "error", "message": f"unknown entity {entity}"})
            continue

        Model = _MODELS[entity]
        existing = db.session.get(Model, op_id) if op_id else None

        try:
            if kind == "delete":
                if existing:
                    db.session.delete(existing)
                    db.session.commit()
                results.append({"op_id": client_op_id, "id": op_id, "entity": entity,
                                "status": "deleted"})
                continue

            data = dict(op.get("data") or {})
            data["id"] = op_id
            base_ts = _parse(op.get("base_updated_at"))
            incoming_ts = _parse(data.get("updated_at"))
            server_ts = _naive(existing.updated_at) if existing else None

            conflict = (
                existing is not None
                and base_ts is not None
                and server_ts is not None
                and server_ts > base_ts
            )

            if conflict and (incoming_ts is None or server_ts >= incoming_ts):
                # Server copy wins — do not overwrite. Return it for adoption.
                results.append({
                    "op_id": client_op_id, "id": op_id, "entity": entity,
                    "status": "conflict_server_wins",
                    "server": existing.to_dict(),
                })
                continue

            obj, created = _APPLIERS[entity](data)
            db.session.commit()
            results.append({
                "op_id": client_op_id, "id": obj.id, "entity": entity,
                "status": "conflict_client_wins" if conflict else ("created" if created else "applied"),
                "server": obj.to_dict(),
            })
        except Exception as exc:  # noqa: BLE001 — report, don't crash the batch
            db.session.rollback()
            results.append({"op_id": client_op_id, "id": op_id, "entity": entity,
                            "status": "error", "message": str(exc)})

    return ok({"results": results, "server_time": datetime.now(timezone.utc).isoformat()})


@api_bp.get("/sync/snapshot")
def snapshot():
    """Full dataset for the client to cache locally (personal-scale data)."""
    return ok({
        "trips": [t.to_dict() for t in Trip.query.all()],
        "catches": [c.to_dict() for c in Catch.query.all()],
        "pins": [p.to_dict() for p in MapPin.query.all()],
        "server_time": datetime.now(timezone.utc).isoformat(),
    })
