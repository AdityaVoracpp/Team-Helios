"""Seed ``app.db`` with a realistic demo queue.

The 200-record corpus in ``hackathon/data/`` is the retrieval corpus for the RAG
service; here we derive a small, deterministic slice of *live* tickets from it so
the admin workbench has something to triage on a cold start.

Usage::

    python seed_db.py           # wipe + reseed
    python seed_db.py --keep    # seed without wiping
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import database as db

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "historical_incidents_200.json"

#: Categories whose records we promote into the live queue, and how many each.
QUEUE_PLAN = {
    "Network & Connectivity": 3,
    "Identity & Access": 2,
    "Hardware & Endpoints": 2,
    "Software & Cloud Applications": 2,
    "Security & Compliance": 1,
}


def load_incidents() -> list[dict]:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def seed(*, reset: bool = True) -> int:
    if reset:
        db.reset_db()

    incidents = load_incidents()
    created = 0
    now = datetime.now(timezone.utc)

    for category, count in QUEUE_PLAN.items():
        picks = [i for i in incidents if i["category"] == category][:count]
        for offset, record in enumerate(picks):
            # Open work sits in the recent past so the queue sorts believably.
            created_at = (now - timedelta(hours=2 * offset + 1)).isoformat(timespec="seconds")
            db.create_ticket(
                record["title"],
                record["description"],
                category=record["category"],
                subcategory=record.get("subcategory", ""),
                priority=record["priority"],
                affected_service=record.get("affected_service", ""),
                assignment_group=record["assignment_group"],
                status="Open" if offset % 3 else "In Progress",
                created_at=created_at,
                audit_data={
                    "source": "seed",
                    "derived_from": record["id"],
                    "symptoms": record.get("symptoms", []),
                    "seeded_at": now.isoformat(timespec="seconds"),
                },
            )
            created += 1

    # Two historical resolved tickets for variety in the queue + feedback demo.
    for record in incidents[60:62]:
        db.create_ticket(
            record["title"],
            record["description"],
            category=record["category"],
            subcategory=record.get("subcategory", ""),
            priority=record["priority"],
            affected_service=record.get("affected_service", ""),
            assignment_group=record["assignment_group"],
            status="Resolved",
            action_steps=record.get("action_steps", []),
            resolution_notes=record.get("resolution_notes", ""),
            audit_data={"source": "seed", "derived_from": record["id"]},
        )
        created += 1

    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the Helios demo database.")
    parser.add_argument("--keep", action="store_true", help="do not wipe existing tickets first")
    args = parser.parse_args()

    count = seed(reset=not args.keep)
    stats = db.get_stats()
    print(f"Seeded {count} tickets into {db.DB_PATH}")
    print(f"Queue: {stats['open']} open · {stats['total']} total · deflection {stats['deflection_rate']:.0%}")


if __name__ == "__main__":
    main()
