# Task board â€” 40 : 40 : 20 Team Allocation

Sprint 0 deliverable: every task assigned, sized, and ordered. Keep this file current â€” it is the shared source of truth for who is doing what, and judges read the repo.

### Team Roles & Workload Distribution
- **Member 1 (40% Capacity): Backend & AI/RAG Engineer** â€” Owns FastAPI endpoints, database models, classification logic, hybrid retrieval engine, RAG resolution synthesis, and audit logs.
- **Member 2 (40% Capacity): Frontend & UI/UX Engineer** â€” Owns React + Tailwind UI, ServiceNow Polaris styling, End-User Self-Service portal with live deflection, Admin KPI dashboard, and Analyst Resolution Workbench.
- **Member 3 (20% Capacity): Data, Evaluation & Pitch Lead (Clock Owner)** â€” Owns seed dataset curation (40 tickets + 10 KBs), the 3 required worked examples, formal Evaluation Report, README documentation, backup demo video, and submission/pitch.

Status values: `todo`, `doing`, `done`, `cut`.

> **Build note (2026-10-31):** the locked design is **single-tier** â€” Streamlit front-end + `database.py` + `rag_service.py` ([system_design.md](system_design.md)). Rows below that mention FastAPI/React/HTTP endpoints describe the original split; they map to `app.py` (UI) and `database.py` (persistence) in the shipped code. App layer is complete and verified; the RAG lane (`rag_service.py`) is the open dependency.

---

## Sprint 0 â€” Setup & Architecture Lock (Target: D-5:00)

| # | Task | Workload | Owner | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0.1 | Framing sentence & rubric criteria mapping | 20% Lane | Member 3 | todo | Aligned with HCLTech brief in README |
| 0.2 | Record stack & database decisions in `DECISIONS.md` | 20% Lane | Member 3 | todo | SQLite + ChromaDB/In-Memory + FastAPI + React |
| 0.3 | Draft API Contract in README (6 core endpoints) | 40% Lane | Member 1 | todo | Ticket intake, predict, similar, resolve, feedback, audit |
| 0.4 | DB schema drafted (`Ticket`, `KB`, `Feedback`, `Audit`) | 40% Lane | Member 1 | todo | SQLite + SQLAlchemy / SQLModel |
| 0.5 | API keys & environment check (`.env.example`) | 40% Lane | Member 1 | todo | Test LLM & embedding API connectivity |
| 0.6 | Scaffold React + Vite + Tailwind repository | 40% Lane | Member 2 | todo | Dark/light ServiceNow theme setup |
| 0.7 | Scaffold base routing (`/portal` vs `/workspace`) | 40% Lane | Member 2 | todo | End-user vs Support Analyst views |
| 0.8 | **Placeholder deployed / cold-run tested** | 40% Lane | Member 2 | todo | Hard stop before Sprint 1 begins |
| 0.9 | Curate seed dataset schema & 10 sample tickets | 20% Lane | Member 3 | todo | Realistic IT incident samples (no KB needed) |

---

## Sprint 1 â€” Core Build & Integration (D-5:00 â†’ D-1:30)

| # | Task | Workload | Owner | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Backend & AI Lane (40%)** | | | | | |
| 1.1 | DB setup & seed loader script (`data/seed.json`) | 40% Lane | Member 1 | done | `database.py` (SQLite) + `seed_db.py`; 1-command reset (`python seed_db.py`) |
| 1.2 | CRUD API endpoints implementation | 40% Lane | Member 1 | done | Single-tier design: `database.py` CRUD functions called directly by `app.py` (no HTTP tier) |
| 1.3 | FR-01: AI Ticket Classification & Confidence module | 40% Lane | Member 1 | todo | Predict Category, Subcategory, Urgency, Priority |
| 1.4 | FR-02: Hybrid Similarity & Duplicate Retrieval | 40% Lane | Member 1 | todo | BM25 keyword + dense vector similarity |
| 1.5 | FR-03 & FR-04: RAG Resolution Recommender & Citations | 40% Lane | Member 1 | todo | Step-by-step playbook + source ticket excerpts |
| 1.6 | FR-05: Confidence guardrail & fallback logic | 40% Lane | Member 1 | todo | Flag confidence < 70% for Tier 2 escalation |
| 1.7 | FR-06 & FR-08: Analyst Feedback & Audit logging APIs | 40% Lane | Member 1 | todo | Store thumbs up/down and full inference trace |
| **Frontend & UI/UX Lane (40%)** | | | | | |
| 1.8 | End-User Portal: Intake form with AI autofill | 40% Lane | Member 2 | done | `app.py` User persona; AI autofill activates when `rag_service.py` is importable |
| 1.9 | End-User Portal: Pre-submission Contextual Deflection | 40% Lane | Member 2 | doing | Radar UI + deflect/create actions shipped; waiting on RAG similarity call |
| 1.10 | Admin Workspace: KPI Dashboard cards | 40% Lane | Member 2 | done | Live SQLite metrics: total, open queue, deflection rate, useful-feedback share |
| 1.11 | Admin Workspace: Filterable Incident Queue (FR-07) | 40% Lane | Member 2 | done | Category / priority / status / assignment-group facets, empty state included |
| 1.12 | Analyst Workbench: Ticket view & AI Copilot drawer | 40% Lane | Member 2 | done | Ticket detail card + resolution panel (renders when RAG available) |
| 1.13 | Analyst Workbench: Citations drawer & Feedback bar | 40% Lane | Member 2 | done | Citation lines per step, Useful/Incorrect/Unresolved buttons persisting to SQLite |
| 1.14 | Audit Trail viewer (FR-08) | 40% Lane | Member 2 | done | `st.json` expander over the ticket `audit_data` column |
| **Data, Evaluation & QA Lane (20%)** | | | | | |
| 1.15 | Complete 30-40 ticket seed dataset (`seed_tickets.json`) | 20% Lane | Member 3 | todo | Realistic ITIL incidents across 5 categories (KB skipped) |
| 1.16 | Document 3 worked submission examples | 20% Lane | Member 3 | todo | Outage deflection, SSO fix, hardware fallback |
| 1.17 | **D-4:00 Integration Checkpoint** | All | Lead: M3 | todo | Real UI calls real API on real seed data |
| 1.18 | **D-3:15 Midpoint Check-in (90-sec pitch)** | 20% Lane | Member 3 | todo | Status to Chapter Members / Mentors |
| 1.19 | Run classification & retrieval quality benchmark | 20% Lane | Member 3 | todo | Measure accuracy % and document error cases |
| 1.20 | UI Polish pass (spacing, loading states, empty states) | 40% Lane | Member 2 | todo | UX is 25% of hackathon score |
| 1.21 | **D-1:45 Hardening Checkpoint** | All | Lead: M1 | todo | Fix bugs on demo path; zero new features |

---

## Sprint 2 â€” Ship, Document & Rehearse (D-1:30 â†’ D-0:00)

| # | Task | Workload | Owner | Status | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 2.1 | **D-1:30 Feature Freeze & Final Build** | 40% Lane | Member 2 | todo | Deploy real app or test local production build |
| 2.2 | **D-1:10 Record Backup Demo Video** | 20% Lane | Member 3 | todo | Essential insurance against live demo failure |
| 2.3 | Write formal Evaluation Report (`EVALUATION.md`) | 20% Lane | Member 3 | todo | Mandatory submission item: results & limitations |
| 2.4 | Finalize Technical Documentation (`README.md`) | 20% Lane | Member 3 | todo | Architecture, setup instructions, assumptions |
| 2.5 | API contract & test verification run | 40% Lane | Member 1 | todo | Verify Swagger `/docs` and all 8 FRs |
| 2.6 | **D-0:30 Submit Final Entry** | 20% Lane | Member 3 | todo | Repo URL, live link, pitch, screenshot proof |
| 2.7 | **D-0:15 Rehearse Pitch Twice** | All | Lead: M3 | todo | Timed walk-through on presenting laptop |

---

## Cut List (Contingency Priority)

If behind schedule at checkpoint gates, cut strictly in this order:

| Task | Cut Priority | Reason |
| :--- | :--- | :--- |
| Multi-user authentication | Priority 1 (Cut First) | Role-toggle button achieves the same demo effect |
| Advanced interactive charts on KPI cards | Priority 2 | Static metric cards are sufficient for demo |
| Seed dataset size (shrink from 40 to 20 tickets) | Priority 3 | 20 well-curated tickets still prove retrieval quality |
| Cloud deployment | Priority 4 | Localhost demo + backup video is 100% valid |
| **The 3 Worked Examples & Citations Panel** | **NEVER CUT** | Core evaluation requirement in the hackathon brief |
