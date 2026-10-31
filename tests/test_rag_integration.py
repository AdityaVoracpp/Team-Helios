"""Integration test: App <-> RAG contract, with the LLM stubbed out.

The RAG unit tests in ``hackathon/tests`` cover retrieval and prompt handling
with fakes. This test sits one level up and proves the *app* wiring: that a
classification result flows into the intake form, that a deflection card can be
accepted and persisted as ``Deflected``, and that a resolution playbook renders
in the analyst workbench.

No API key or network access is required — the RAG service methods are replaced
with fixtures, so this runs in CI and on a plane.

Run with::

    python tests/test_rag_integration.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP_DB = Path(tempfile.mkdtemp(prefix="helios-rag-test-")) / "test.db"
os.environ["HELIOS_DB_PATH"] = str(_TMP_DB)

from streamlit.testing.v1 import AppTest  # noqa: E402

import database as db  # noqa: E402
from hackathon import rag_service  # noqa: E402


def _classification() -> "rag_service.ClassificationResult":
    return rag_service.ClassificationResult(
        category="Network & Connectivity",
        subcategory="VPN Client",
        priority="P2",
        urgency="High - single user blocked",
        confidence_score=0.91,
        reasoning="Explicit AnyConnect 504 handshake failure matches the VPN client precedent.",
    )


def _deflection() -> "rag_service.DeflectionResult":
    return rag_service.DeflectionResult(
        deflection_suggested=True,
        similar_tickets=[
            rag_service.SimilarTicket(
                id="INC002491",
                title="Cisco AnyConnect VPN disconnected with Error 504 Gateway Timeout",
                similarity_score=0.88,
                status="Resolved",
                resolution_summary="Flushed DNS cache and reinstalled the TAP driver.",
                quick_workaround="Run 'ipconfig /flushdns' in an elevated prompt, then reconnect.",
            )
        ],
    )


def _resolution() -> "rag_service.ResolutionResult":
    citation = rag_service.Citation(
        ticket_id="INC002491",
        similarity_score=0.88,
        excerpt="Run 'ipconfig /flushdns' in elevated Command Prompt",
    )
    return rag_service.ResolutionResult(
        is_low_confidence=False,
        confidence_score=0.88,
        playbook_steps=[
            rag_service.PlaybookStep(
                step_number=1,
                action="Run 'ipconfig /flushdns' in elevated Command Prompt",
                rationale="Clears the stale DNS entry seen in the precedent.",
                source_citation=citation,
            )
        ],
        summary_notes="DNS cache flush restored connectivity in the source incident.",
        audit_trace={"retrieved_ids": ["INC002491"], "model": "stub"},
    )


def _button(at: AppTest, fragment: str):
    matches = [b for b in at.button if fragment in b.label]
    assert matches, f"no button containing {fragment!r}; saw {[b.label for b in at.button]}"
    return matches[0]


def main() -> int:
    db.reset_db()

    def fake_init(self, data_path=None):  # noqa: ANN001 - mirrors real signature loosely
        self.data_path = data_path

    with patch.object(rag_service.RAGService, "__init__", fake_init), patch.object(
        rag_service.RAGService, "classify_ticket", lambda self, *a, **k: _classification()
    ), patch.object(
        rag_service.RAGService, "find_similar_and_deflect", lambda self, *a, **k: _deflection()
    ), patch.object(
        rag_service.RAGService, "recommend_resolution", lambda self, *a, **k: _resolution()
    ):
        at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
        at.run()
        assert not at.exception, f"boot failed: {[e.message for e in at.exception]}"

        # ---- intake with a live (stubbed) classification ---------------------
        at.text_input[0].set_value("VPN drops with Error 504")
        at.text_area[0].set_value("AnyConnect handshake fails with 504 from home")
        at.text_input[1].set_value("Cisco AnyConnect")
        _button(at, "Analyze Issue").click().run()
        assert not at.exception, [e.message for e in at.exception]
        metrics = {m.label: m.value for m in at.metric}
        assert metrics.get("Suggested category") == "Network & Connectivity", metrics
        assert metrics.get("Confidence") == "91%", metrics
        radar = " ".join(str(m.value) for m in at.markdown)
        assert "Cisco AnyConnect" in radar, "deflection radar card missing"
        assert "match" in radar, "similarity badge missing"
        print("OK  classification rendered (category, priority, confidence, reasoning)")

        # ---- deflection path ------------------------------------------------
        _button(at, "This solved my problem").click().run()
        assert not at.exception, [e.message for e in at.exception]
        rows = db.get_all_tickets()
        assert len(rows) == 1, rows
        ticket = rows[0]
        assert ticket["status"] == "Deflected", ticket["status"]
        assert ticket["category"] == "Network & Connectivity", ticket["category"]
        assert ticket["assignment_group"] == "Network Operations", ticket["assignment_group"]
        assert ticket["resolution_notes"], "deflection should carry the workaround into notes"
        print("OK  deflection persisted as Deflected with workaround + derived group")

        # ---- analyst workbench: playbook + citations ------------------------
        db.create_ticket(
            "VPN drops with Error 504",
            "AnyConnect handshake fails with 504",
            category="Network & Connectivity",
            priority="P2 - High",
            assignment_group="Network Operations",
        )
        at.radio[0].set_value("Admin (Support Workbench)").run()
        assert not at.exception, [e.message for e in at.exception]
        _button(at, "Generate resolution playbook").click().run()
        assert not at.exception, [e.message for e in at.exception]
        assert "INC002491" in at.markdown[-1].value or any(
            "INC002491" in str(m.value) for m in at.markdown
        ), "citation ticket id should be rendered"
        print("OK  resolution playbook rendered with source citation")

        # ---- audit trace carries the AI payload -----------------------------
        audit = db.get_all_tickets(status="Deflected")[0]["audit_data"]
        assert audit["agent_mode"] == "ai", audit
        assert audit["classification"]["category"] == "Network & Connectivity", audit
        print("OK  audit trace stores the AI classification payload")

    print("\nAll RAG-integration checks passed (LLM stubbed, no network).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
