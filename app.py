"""Helios ITSM Assist — Streamlit front-end and application logic.

Single-tier design per ``hackathon/system_design.md``: this file owns the UI and
calls ``database.py`` directly for persistence. All AI/retrieval work is delegated
to ``rag_service.py`` (built separately); if that module is not present yet the
app degrades gracefully to a manual-triage flow instead of crashing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st
from dotenv import load_dotenv

import database as db

load_dotenv()

ROOT = Path(__file__).resolve().parent
DATASET_PATH = ROOT / "historical_incidents_200.json"

# --------------------------------------------------------------------------- #
# Optional RAG subsystem (owned by the RAG lane — import must never break the UI)
# --------------------------------------------------------------------------- #
try:  # pragma: no cover - depends on whether rag_service.py has landed
    import rag_service  # type: ignore

    RAG_ERROR: str | None = None
except Exception as exc:  # noqa: BLE001 - any import failure degrades to manual mode
    rag_service = None  # type: ignore[assignment]
    RAG_ERROR = f"{type(exc).__name__}: {exc}"

RAG_AVAILABLE = rag_service is not None


@st.cache_resource(show_spinner=False)
def get_rag_service() -> Any | None:
    """Instantiate the RAG service once per Streamlit process."""
    if not RAG_AVAILABLE:
        return None
    try:
        return rag_service.RAGService(data_path=str(DATASET_PATH))
    except Exception as exc:  # noqa: BLE001 - surfaced in the sidebar, never fatal
        st.session_state["rag_runtime_error"] = f"{type(exc).__name__}: {exc}"
        return None


# --------------------------------------------------------------------------- #
# Taxonomy (read from the corpus so the UI can never drift from the data)
# --------------------------------------------------------------------------- #
FALLBACK_CATEGORIES = [
    "Network & Connectivity",
    "Identity & Access",
    "Hardware & Endpoints",
    "Software & Cloud Applications",
    "Security & Compliance",
]
PRIORITIES = ["P1 - Critical", "P2 - High", "P3 - Medium", "P4 - Low"]
FALLBACK_GROUP_BY_CATEGORY = {
    "Network & Connectivity": "Network Operations",
    "Identity & Access": "Identity & Access Management",
    "Hardware & Endpoints": "Desktop & End User Support",
    "Software & Cloud Applications": "Enterprise Application Support",
    "Security & Compliance": "Security Operations Center",
}


@st.cache_data(show_spinner=False)
def load_taxonomy() -> dict[str, Any]:
    """Derive categories, assignment groups and their mapping from the corpus.

    Read from data rather than hardcoded so the UI can never drift from the
    dataset or from what ``rag_service.py`` classifies against. Falls back to
    the canonical lists when the corpus is unavailable.
    """
    try:
        records = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - corpus is optional for manual triage
        return {
            "categories": FALLBACK_CATEGORIES,
            "groups": sorted(set(FALLBACK_GROUP_BY_CATEGORY.values())),
            "group_by_category": FALLBACK_GROUP_BY_CATEGORY,
        }

    categories = sorted({r["category"] for r in records})
    groups = sorted({r["assignment_group"] for r in records})

    # Majority assignment group per category (the corpus currently maps 1:1).
    tally: dict[str, dict[str, int]] = {}
    for record in records:
        bucket = tally.setdefault(record["category"], {})
        bucket[record["assignment_group"]] = bucket.get(record["assignment_group"], 0) + 1
    group_by_category = {
        category: max(counts, key=counts.get) for category, counts in tally.items()
    }

    return {
        "categories": categories or FALLBACK_CATEGORIES,
        "groups": groups or sorted(set(FALLBACK_GROUP_BY_CATEGORY.values())),
        "group_by_category": group_by_category or FALLBACK_GROUP_BY_CATEGORY,
    }


# --------------------------------------------------------------------------- #
# Page setup + styling
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="Helios ITSM Assist",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

_CSS = """
<style>
  .block-container { padding-top: 2.2rem; max-width: 1180px; }
  .helios-hero { font-size: 1.65rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: .1rem; }
  .helios-sub { color: #6b7280; font-size: .92rem; margin-bottom: 1.1rem; }
  .helios-card {
      border: 1px solid #e5e7eb; border-radius: 12px; padding: 1rem 1.1rem;
      background: #ffffff; margin-bottom: .75rem;
  }
  .helios-pill {
      display: inline-block; padding: .15rem .55rem; border-radius: 999px;
      font-size: .74rem; font-weight: 600; margin-right: .35rem;
      background: #eef2ff; color: #3730a3;
  }
  .helios-pill-warn { background: #fef3c7; color: #92400e; }
  .helios-pill-ok { background: #dcfce7; color: #166534; }
  .helios-step {
      border-left: 3px solid #6366f1; padding: .1rem 0 .1rem .8rem; margin-bottom: .7rem;
  }
  .helios-cite { color: #6b7280; font-size: .78rem; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)


def _pill(text: str, kind: str = "") -> str:
    cls = "helios-pill" + (f" helios-pill-{kind}" if kind else "")
    return f'<span class="{cls}">{text}</span>'


def _render_header() -> None:
    st.markdown('<div class="helios-hero">🛰️ Helios ITSM Assist</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="helios-sub">Enterprise IT intelligence — classify, deflect, resolve, and trace every ticket.</div>',
        unsafe_allow_html=True,
    )


def _flash() -> None:
    """Show a one-shot success message after a rerun."""
    message = st.session_state.pop("flash", None)
    if message:
        st.success(message)


# --------------------------------------------------------------------------- #
# User persona — intake, analysis, deflection
# --------------------------------------------------------------------------- #
def _analysis_payload() -> dict[str, Any] | None:
    return st.session_state.get("intake_payload")


def _run_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    """Call the RAG service if present; otherwise return a manual-mode result."""
    service = get_rag_service()
    result: dict[str, Any] = {
        "mode": "manual",
        "classification": None,
        "deflection": None,
        "error": None,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if service is None:
        return result

    try:
        classification = service.classify_ticket(
            payload["title"], payload["description"], payload["affected_service"] or None
        )
        result["mode"] = "ai"
        result["classification"] = classification.model_dump()
    except Exception as exc:  # noqa: BLE001 - a failed call must not block intake
        result["error"] = f"Classification failed: {type(exc).__name__}: {exc}"
        return result

    try:
        deflection = service.find_similar_and_deflect(
            payload["title"], payload["description"], payload["affected_service"] or None, top_k=3
        )
        result["deflection"] = deflection.model_dump()
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Similarity search failed: {type(exc).__name__}: {exc}"

    return result


def _resolve_classification(payload: dict[str, Any], analysis: dict[str, Any]) -> tuple[str, str, str, str]:
    """Pick the effective (category, subcategory, priority, group) for the ticket."""
    classification = analysis.get("classification") or {}
    category = classification.get("category") or payload.get("manual_category") or "Unclassified"
    subcategory = classification.get("subcategory") or ""
    priority = classification.get("priority") or payload.get("manual_priority") or "P3 - Medium"
    group = load_taxonomy()["group_by_category"].get(category, "Service Desk")
    return category, subcategory, priority, group


def _save_ticket(payload: dict[str, Any], analysis: dict[str, Any], *, deflect: bool, similar: dict | None) -> str:
    category, subcategory, priority, group = _resolve_classification(payload, analysis)
    notes = ""
    steps: list[str] = []
    if deflect and similar:
        notes = similar.get("resolution_summary") or similar.get("quick_workaround") or ""
        steps = [similar["quick_workaround"]] if similar.get("quick_workaround") else []

    ticket_id = db.create_ticket(
        payload["title"],
        payload["description"],
        category=category,
        subcategory=subcategory,
        priority=priority,
        affected_service=payload["affected_service"],
        assignment_group=group,
        status="Deflected" if deflect else "Open",
        action_steps=steps,
        resolution_notes=notes,
        audit_data={
            "source": "employee_intake",
            "agent_mode": analysis["mode"],
            "classification": analysis.get("classification"),
            "deflection": analysis.get("deflection"),
            "error": analysis.get("error"),
            "generated_at": analysis["generated_at"],
        },
    )
    st.session_state.pop("intake_payload", None)
    st.session_state["form_version"] = st.session_state.get("form_version", 0) + 1
    return ticket_id


def user_view() -> None:
    categories = load_taxonomy()["categories"]
    st.subheader("Report an issue")
    st.caption(
        "Describe the problem in your own words. The assistant checks it against past incidents "
        "before you submit."
    )

    version = st.session_state.get("form_version", 0)
    with st.form(f"intake_form_{version}", clear_on_submit=False):
        title = st.text_input("Short description", placeholder="Laptop cannot reach internal sites over VPN")
        description = st.text_area(
            "What exactly is happening?",
            placeholder="AnyConnect connects but times out with error 504. Browser shows no internal pages.",
            height=110,
        )
        affected_service = st.text_input("Affected service (optional)", placeholder="Cisco AnyConnect")
        col_a, col_b = st.columns(2)
        with col_a:
            manual_category = st.selectbox("Category (leave blank to let the assistant decide)", [""] + categories)
        with col_b:
            manual_priority = st.selectbox("Priority (optional)", [""] + PRIORITIES)
        analyze = st.form_submit_button("Analyze Issue", type="primary", width="stretch")

    if analyze:
        if not title.strip() or not description.strip():
            st.error("A short description and details are both required.")
        else:
            payload = {
                "title": title.strip(),
                "description": description.strip(),
                "affected_service": affected_service.strip(),
                "manual_category": manual_category,
                "manual_priority": manual_priority,
            }
            with st.spinner("Checking against 200 historical incidents…"):
                analysis = _run_analysis(payload)
            payload["analysis"] = analysis
            st.session_state["intake_payload"] = payload

    payload = _analysis_payload()
    if not payload:
        return

    analysis = payload["analysis"]
    classification = analysis.get("classification")
    st.divider()

    if analysis["mode"] == "manual":
        st.warning(
            "**AI service not connected.** `rag_service.py` is not importable yet, so this ticket "
            "will be created as manual triage and queued for an analyst.",
            icon="⚠️",
        )
    if analysis.get("error"):
        st.error(analysis["error"], icon="🛑")

    if classification:
        c1, c2, c3 = st.columns(3)
        c1.metric("Suggested category", classification["category"])
        c2.metric("Suggested priority", classification["priority"])
        c3.metric("Confidence", f"{classification['confidence_score'] * 100:.0f}%")
        st.caption(f"**Why:** {classification.get('reasoning', '—')}")

    similar_tickets = (analysis.get("deflection") or {}).get("similar_tickets") or []
    if similar_tickets:
        st.markdown("#### 🔎 Deflection radar")
        st.caption("Resolved incidents that look like yours — try these before raising a ticket.")
        for item in similar_tickets:
            score = item.get("similarity_score", 0.0)
            with st.container(border=True):
                cols = st.columns([4, 1])
                cols[0].markdown(f"**{item.get('title', 'Untitled')}**")
                cols[1].markdown(f"`{score * 100:.0f}% match`")
                if item.get("quick_workaround"):
                    st.markdown(f"**Try this first:** {item['quick_workaround']}")
                st.caption(
                    f"{item.get('id', '—')} · {item.get('status', '—')} · "
                    f"{item.get('resolution_summary', '')[:180]}"
                )

    st.markdown("#### Next step")
    b1, b2 = st.columns(2)
    deflect = b1.button(
        "✅ This solved my problem",
        type="primary",
        width="stretch",
        disabled=not similar_tickets,
    )
    submit = b2.button("📨 Submit incident anyway", width="stretch")

    if deflect and similar_tickets:
        ticket_id = _save_ticket(payload, analysis, deflect=True, similar=similar_tickets[0])
        st.session_state["flash"] = f"Deflected — closed {ticket_id} from self-service. No incident raised."
        st.rerun()
    if submit:
        ticket_id = _save_ticket(payload, analysis, deflect=False, similar=None)
        st.session_state["flash"] = f"Incident {ticket_id} created and queued for an analyst."
        st.rerun()


# --------------------------------------------------------------------------- #
# Admin persona — queue, workbench, feedback, audit
# --------------------------------------------------------------------------- #
def _queue_filters() -> tuple[list[str], list[str], str, str]:
    taxonomy = load_taxonomy()
    categories, groups = taxonomy["categories"], taxonomy["groups"]
    stats = db.get_stats()
    live_categories = sorted(stats["by_category"]) or categories

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        sel_categories = c1.multiselect("Category", live_categories, default=[])
        sel_priorities = c2.multiselect("Priority", PRIORITIES, default=[])
        sel_status = c3.selectbox("Status", ["Any", *db.STATUSES], index=0)
        sel_group = c4.selectbox("Assignment group", ["Any", *groups], index=0)
    return (
        sel_categories,
        sel_priorities,
        "" if sel_status == "Any" else sel_status,
        "" if sel_group == "Any" else sel_group,
    )


def _ticket_label(ticket: dict[str, Any]) -> str:
    return f"{ticket['id']} · {ticket['title'][:70]} · {ticket['priority']}"


def admin_view() -> None:
    stats = db.get_stats()
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total tickets", stats["total"])
    k2.metric("Open queue", stats["open"])
    k3.metric("Deflection rate", f"{stats['deflection_rate'] * 100:.0f}%", help="Deflected ÷ (submitted + deflected)")
    k4.metric(
        "Useful feedback",
        f"{stats['useful_rate'] * 100:.0f}%" if stats["rated"] else "—",
        help="Share of rated AI suggestions marked Useful",
    )

    st.subheader("Incident queue")
    categories, priorities, status, group = _queue_filters()
    tickets = db.get_all_tickets(
        categories=categories,
        priorities=priorities,
        status=status or None,
        assignment_group=group or None,
    )

    if not tickets:
        st.info("No tickets match these filters yet. Submit one from the Employee Center persona.")
        return

    st.dataframe(
        [
            {
                "ID": t["id"],
                "Title": t["title"],
                "Category": t["category"],
                "Priority": t["priority"],
                "Status": t["status"],
                "Group": t["assignment_group"],
                "Feedback": t["feedback_status"] or "—",
            }
            for t in tickets
        ],
        width="stretch",
        hide_index=True,
    )

    ids = [t["id"] for t in tickets]
    selected_id = st.selectbox("Open ticket", ids, index=0, format_func=lambda i: _ticket_label(next(t for t in tickets if t["id"] == i)))
    ticket = db.get_ticket(selected_id)
    if not ticket:
        st.error("Ticket disappeared — refreshing.")
        return
    _ticket_detail(ticket)


def _ticket_detail(ticket: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"### {ticket['title']}")
        st.markdown(
            _pill(ticket["id"])
            + _pill(ticket["category"])
            + _pill(ticket["priority"], "warn" if ticket["priority"].startswith("P1") else "")
            + _pill(ticket["status"], "ok" if ticket["status"] in ("Resolved", "Closed") else "")
            + _pill(ticket["assignment_group"]),
            unsafe_allow_html=True,
        )
        st.write(ticket["description"] or "_No description provided._")
        st.caption(f"Created {ticket['created_at']} · Service: {ticket['affected_service'] or '—'}")

    st.subheader("AI resolution assistant")
    if not RAG_AVAILABLE:
        st.info(
            "`rag_service.py` is not available yet. The workbench still supports triage, feedback, "
            "and audit review — resolution playbooks will appear here once the RAG lane lands."
        )
    else:
        _resolution_panel(ticket)

    _feedback_panel(ticket)

    with st.expander("🔍 AI audit & explainability"):
        st.json(ticket["audit_data"] or {})


def _resolution_panel(ticket: dict[str, Any]) -> None:
    if st.button("Generate resolution playbook", type="primary"):
        service = get_rag_service()
        if service is None:
            st.error(st.session_state.get("rag_runtime_error", "RAG service unavailable."))
            return
        with st.spinner("Retrieving precedents…"):
            try:
                result = service.recommend_resolution(ticket, top_k=3)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Resolution failed: {type(exc).__name__}: {exc}")
                return
        st.session_state[f"resolution_{ticket['id']}"] = result.model_dump()

    resolution = st.session_state.get(f"resolution_{ticket['id']}")
    if not resolution:
        return

    if resolution.get("is_low_confidence"):
        st.warning(
            f"**{resolution.get('fallback_reason', 'Low confidence')}**  \n"
            f"Escalate to: `{resolution.get('escalation_group', 'Tier 2')}`",
            icon="⚠️",
        )
        return

    st.progress(min(max(resolution.get("confidence_score", 0.0), 0.0), 1.0))
    st.caption(f"Confidence {resolution.get('confidence_score', 0) * 100:.0f}%")

    for step in resolution.get("playbook_steps", []):
        citation = step.get("source_citation") or {}
        st.markdown(
            f'<div class="helios-step"><strong>{step.get("step_number", "•")}. {step.get("action", "")}</strong>'
            f'<div>{step.get("rationale", "")}</div>'
            f'<div class="helios-cite">Source {citation.get("ticket_id", "—")} · '
            f'{citation.get("similarity_score", 0) * 100:.0f}% · "{citation.get("excerpt", "")[:160]}"</div></div>',
            unsafe_allow_html=True,
        )

    if resolution.get("summary_notes"):
        st.caption(f"**Summary:** {resolution['summary_notes']}")

    if st.button("Apply fix to ticket", width="content"):
        db.update_resolution(
            ticket["id"],
            status="Resolved",
            action_steps=[s.get("action", "") for s in resolution.get("playbook_steps", [])],
            resolution_notes=resolution.get("summary_notes", ""),
        )
        st.session_state["flash"] = f"{ticket['id']} marked Resolved with the AI playbook."
        st.rerun()


def _feedback_panel(ticket: dict[str, Any]) -> None:
    st.markdown("#### Was this helpful?")
    if ticket["feedback_status"]:
        st.caption(f"Last feedback: **{ticket['feedback_status']}** — {ticket['feedback_notes'] or 'no note'}")
    c1, c2, c3 = st.columns(3)
    choice = None
    if c1.button("👍 Useful", width="stretch"):
        choice = "useful"
    if c2.button("👎 Incorrect", width="stretch"):
        choice = "incorrect"
    if c3.button("❓ Unresolved", width="stretch"):
        choice = "unresolved"
    if choice:
        db.update_feedback(ticket["id"], choice)
        st.session_state["flash"] = f"Feedback recorded for {ticket['id']}: {choice}."
        st.rerun()


# --------------------------------------------------------------------------- #
# Shell
# --------------------------------------------------------------------------- #
def main() -> None:
    db.init_db()
    _render_header()

    with st.sidebar:
        st.markdown("### Helios ITSM Assist")
        st.caption("HCLTech · Future Ready AI Engineer Hackathon")
        persona = st.radio(
            "Select Active Persona",
            ["User (Employee Center)", "Admin (Support Workbench)"],
            index=0,
        )
        st.divider()
        if RAG_AVAILABLE:
            st.markdown(_pill("RAG service: connected", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(_pill("RAG service: not installed", "warn"), unsafe_allow_html=True)
            st.caption(RAG_ERROR or "rag_service.py missing")
        st.divider()
        st.caption(f"Database: `{db.DB_PATH.name}`")
        if st.button("Reset demo data", width="stretch", help="Deletes every ticket in app.db"):
            db.reset_db()
            st.session_state.clear()
            st.session_state["flash"] = "Demo data reset — the queue is empty."
            st.rerun()

    _flash()
    if persona.startswith("User"):
        user_view()
    else:
        admin_view()

    st.divider()
    st.caption("Helios ITSM Assist · single-tier Streamlit app · SQLite · retrieval-grounded AI")


main()
