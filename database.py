"""SQLite persistence layer for Helios ITSM Assist.

Single-tier design: the Streamlit UI (``app.py``) imports this module directly.
There is no API tier and no ORM — the schema is small enough that plain
``sqlite3`` with row factories is easier to reason about and has zero setup cost.

Schema mirrors ``hackathon/system_design.md`` §6.1. Every ticket also stores the
AI audit trace as JSON so the workbench can render it without a second table.
"""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

#: ``app.db`` next to this file unless HELIOS_DB_PATH overrides it.
DB_PATH = Path(os.getenv("HELIOS_DB_PATH") or Path(__file__).with_name("app.db"))

STATUSES: tuple[str, ...] = ("Open", "In Progress", "Resolved", "Closed", "Deflected")
FEEDBACK_STATUSES: tuple[str, ...] = ("useful", "incorrect", "unresolved")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    category         TEXT NOT NULL DEFAULT 'Unclassified',
    subcategory      TEXT NOT NULL DEFAULT '',
    priority         TEXT NOT NULL DEFAULT 'P3 - Medium',
    affected_service TEXT NOT NULL DEFAULT '',
    assignment_group TEXT NOT NULL DEFAULT 'Service Desk',
    status           TEXT NOT NULL DEFAULT 'Open',
    created_at       TEXT NOT NULL,
    action_steps     TEXT NOT NULL DEFAULT '[]',   -- JSON array
    resolution_notes TEXT NOT NULL DEFAULT '',
    feedback_status  TEXT NOT NULL DEFAULT '',
    feedback_notes   TEXT NOT NULL DEFAULT '',
    audit_data       TEXT NOT NULL DEFAULT '{}'    -- JSON object
);
CREATE INDEX IF NOT EXISTS idx_tickets_status   ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);
CREATE INDEX IF NOT EXISTS idx_tickets_priority ON tickets(priority);
"""

_JSON_COLUMNS = ("action_steps", "audit_data")


# --------------------------------------------------------------------------- #
# Connection helpers
# --------------------------------------------------------------------------- #
def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and always closes."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init_db() -> None:
    """Create the database file and schema if they do not exist yet."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript(_SCHEMA)


# --------------------------------------------------------------------------- #
# Mapping helpers
# --------------------------------------------------------------------------- #
def _row_to_ticket(row: sqlite3.Row) -> dict[str, Any]:
    ticket = dict(row)
    for column in _JSON_COLUMNS:
        raw = ticket.get(column) or ("[]" if column == "action_steps" else "{}")
        try:
            ticket[column] = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            ticket[column] = [] if column == "action_steps" else {}
    return ticket


def _next_ticket_id(conn: sqlite3.Connection) -> str:
    """Sequential ``INC000001``-style ids, derived from the highest existing one."""
    row = conn.execute(
        "SELECT id FROM tickets WHERE id LIKE 'INC%' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return "INC000001"
    try:
        return f"INC{int(row['id'][3:]) + 1:06d}"
    except ValueError:  # pragma: no cover - defensive against hand-edited rows
        return f"INC{int(datetime.now().timestamp()):06d}"


# --------------------------------------------------------------------------- #
# CRUD
# --------------------------------------------------------------------------- #
def create_ticket(
    title: str,
    description: str,
    *,
    category: str = "Unclassified",
    subcategory: str = "",
    priority: str = "P3 - Medium",
    affected_service: str = "",
    assignment_group: str = "Service Desk",
    status: str = "Open",
    action_steps: Sequence[str] | None = None,
    resolution_notes: str = "",
    audit_data: dict[str, Any] | None = None,
    ticket_id: str | None = None,
    created_at: str | None = None,
) -> str:
    """Insert one ticket and return its id."""
    if not title.strip():
        raise ValueError("title must not be empty")
    if status not in STATUSES:
        raise ValueError(f"unknown status: {status!r}")

    init_db()
    with connect() as conn:
        new_id = ticket_id or _next_ticket_id(conn)
        conn.execute(
            """
            INSERT INTO tickets (
                id, title, description, category, subcategory, priority,
                affected_service, assignment_group, status, created_at,
                action_steps, resolution_notes, feedback_status, feedback_notes,
                audit_data
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                new_id,
                title.strip(),
                description.strip(),
                category,
                subcategory,
                priority,
                affected_service,
                assignment_group,
                status,
                created_at or _utc_now(),
                json.dumps(list(action_steps or [])),
                resolution_notes,
                "",
                "",
                json.dumps(audit_data or {}, default=str),
            ),
        )
        return new_id


def get_ticket(ticket_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return _row_to_ticket(row) if row else None


def get_all_tickets(
    *,
    categories: Iterable[str] | None = None,
    priorities: Iterable[str] | None = None,
    status: str | None = None,
    assignment_group: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return tickets newest-first, filtered by any of the facet values."""
    init_db()
    clauses: list[str] = []
    params: list[Any] = []

    def add_in(column: str, values: Iterable[str] | None) -> None:
        values = [v for v in (values or []) if v]
        if values:
            clauses.append(f"{column} IN ({','.join('?' * len(values))})")
            params.extend(values)

    add_in("category", categories)
    add_in("priority", priorities)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if assignment_group:
        clauses.append("assignment_group = ?")
        params.append(assignment_group)

    sql = "SELECT * FROM tickets"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY created_at DESC, id DESC"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)

    with connect() as conn:
        return [_row_to_ticket(r) for r in conn.execute(sql, params).fetchall()]


def update_feedback(ticket_id: str, status: str, notes: str = "") -> None:
    """Record analyst feedback (FR-06) on an existing ticket."""
    if status not in FEEDBACK_STATUSES:
        raise ValueError(f"unknown feedback status: {status!r}")
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE tickets SET feedback_status = ?, feedback_notes = ? WHERE id = ?",
            (status, notes, ticket_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(ticket_id)


def update_resolution(
    ticket_id: str,
    *,
    status: str | None = None,
    action_steps: Sequence[str] | None = None,
    resolution_notes: str | None = None,
) -> None:
    """Apply an AI/drafted resolution to a ticket."""
    updates: list[str] = []
    params: list[Any] = []
    if status is not None:
        if status not in STATUSES:
            raise ValueError(f"unknown status: {status!r}")
        updates.append("status = ?")
        params.append(status)
    if action_steps is not None:
        updates.append("action_steps = ?")
        params.append(json.dumps(list(action_steps)))
    if resolution_notes is not None:
        updates.append("resolution_notes = ?")
        params.append(resolution_notes)
    if not updates:
        return
    params.append(ticket_id)
    with connect() as conn:
        conn.execute(f"UPDATE tickets SET {', '.join(updates)} WHERE id = ?", params)


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def get_stats() -> dict[str, Any]:
    """Live queue metrics for the admin KPI cards (never hardcoded)."""
    init_db()
    with connect() as conn:
        def scalar(sql: str, params: Sequence[Any] = ()) -> int:
            return int(conn.execute(sql, params).fetchone()[0])

        total = scalar("SELECT COUNT(*) FROM tickets")
        open_count = scalar("SELECT COUNT(*) FROM tickets WHERE status IN ('Open','In Progress')")
        resolved = scalar("SELECT COUNT(*) FROM tickets WHERE status IN ('Resolved','Closed')")
        deflected = scalar("SELECT COUNT(*) FROM tickets WHERE status = 'Deflected'")
        useful = scalar("SELECT COUNT(*) FROM tickets WHERE feedback_status = 'useful'")
        rated = scalar("SELECT COUNT(*) FROM tickets WHERE feedback_status != ''")
        by_category = conn.execute(
            "SELECT category, COUNT(*) AS n FROM tickets GROUP BY category ORDER BY n DESC"
        ).fetchall()

    attempted = total + deflected  # deflected tickets never became incidents
    return {
        "total": total,
        "open": open_count,
        "resolved": resolved,
        "deflected": deflected,
        "deflection_rate": (deflected / attempted) if attempted else 0.0,
        "useful_rate": (useful / rated) if rated else 0.0,
        "rated": rated,
        "by_category": {r["category"]: r["n"] for r in by_category},
    }


def reset_db() -> None:
    """Drop every ticket. Used by ``seed_db.py`` for a clean demo reset."""
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM tickets")


if __name__ == "__main__":  # tiny smoke test: python database.py
    reset_db()
    ticket = create_ticket("VPN drops", "AnyConnect 504 on connect", category="Network & Connectivity")
    print("created", ticket, "->", get_ticket(ticket)["status"])
    update_feedback(ticket, "useful", "confirmed")
    print("stats", get_stats())
