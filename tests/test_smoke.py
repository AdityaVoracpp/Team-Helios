"""End-to-end smoke test for the Helios ITSM Assist app layer.

Runs the real Streamlit script through ``streamlit.testing.v1.AppTest`` — no
server, no browser — and asserts the demo path end to end:

    intake -> analyse (manual mode when RAG credentials are unavailable) -> submit
    -> admin queue -> analyst feedback -> SQLite persists

Run with::

    python tests/test_smoke.py

Exit code 0 means every checkpoint passed.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Point the app at a throwaway database before anything imports `database`.
_TMP_DB = Path(tempfile.mkdtemp(prefix="helios-test-")) / "test.db"
os.environ["HELIOS_DB_PATH"] = str(_TMP_DB)
# Keep this app-layer smoke test offline even when a developer has a real key in .env.
os.environ["OPENAI_API_KEY"] = ""

from streamlit.testing.v1 import AppTest  # noqa: E402

import database as db  # noqa: E402


def _button(at: AppTest, fragment: str):
    matches = [b for b in at.button if fragment in b.label]
    assert matches, f"no button containing {fragment!r}; saw {[b.label for b in at.button]}"
    return matches[0]


def main() -> int:
    db.reset_db()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.run()
    assert not at.exception, f"app crashed on first run: {list(at.exception)}"
    print("OK  app boots with no exception")

    # ---- Employee Center: step 1 (describe) -------------------------------------
    at.text_input[0].set_value("VPN drops with Error 504")
    at.text_area[0].set_value("AnyConnect handshake fails with 504 from home; internal sites unreachable")
    at.text_input[1].set_value("Cisco AnyConnect")
    _button(at, "Next").click().run()
    assert not at.exception, list(at.exception)
    assert at.warning, "expected the 'AI service not connected' banner in manual mode"
    assert [s.label for s in at.selectbox][:2] == ["Category", "Priority"], [s.label for s in at.selectbox]

    # ---- step 2 (review auto-filled fields, override manually) -------------------
    at.selectbox[0].set_value("Network & Connectivity")
    at.selectbox[1].set_value("P2 - High")
    _button(at, "Submit incident anyway").click().run()
    assert not at.exception, list(at.exception)

    rows = db.get_all_tickets()
    assert len(rows) == 1, rows
    ticket = rows[0]
    assert ticket["title"] == "VPN drops with Error 504", ticket
    assert ticket["status"] == "Open", ticket["status"]
    assert ticket["category"] == "Network & Connectivity", ticket["category"]
    assert ticket["priority"] == "P2 - High", ticket["priority"]
    assert ticket["assignment_group"] == "Network Operations", ticket["assignment_group"]
    assert ticket["audit_data"].get("source") == "employee_intake", ticket["audit_data"]
    print(f"OK  intake created {ticket['id']} with taxonomy + audit trace")

    # ---- Admin: queue, filters, feedback ----------------------------------------
    at.radio[0].set_value("Admin (Support Workbench)").run()
    assert not at.exception, list(at.exception)

    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Total tickets"] == "1", metrics
    assert metrics["Open queue"] == "1", metrics
    assert at.dataframe, "queue table missing"
    print("OK  admin KPI cards + queue render from SQLite")

    _button(at, "Useful").click().run()
    assert not at.exception, list(at.exception)
    assert db.get_ticket(ticket["id"])["feedback_status"] == "useful"
    print("OK  analyst feedback persisted")

    # ---- Filters ----------------------------------------------------------------
    at.selectbox[0].set_value("Deflected").run()  # Status filter
    assert not at.exception, list(at.exception)
    assert not at.dataframe, "queue should be empty after filtering to Deflected"
    assert at.info, "expected the empty-state message"
    print("OK  status filter excludes non-matching tickets")

    # ---- Reset control ----------------------------------------------------------
    at.selectbox[0].set_value("Any").run()
    _button(at, "Reset demo data").click().run()
    assert db.get_stats()["total"] == 0
    print("OK  reset clears the ticket table")

    print("\nAll app-layer checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
