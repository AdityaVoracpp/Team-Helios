# Decisions log

One line per lasting decision: date, decision, reason. Append; do not rewrite history. This is what you cite when a judge asks why the architecture looks the way it does.

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-10-31 | Team task allocation set to 40% Backend/AI (Member 1), 40% Frontend/UX (Member 2), 20% Data/Evaluation/Pitch (Member 3) | Balances technical build with mandatory hackathon non-code deliverables (Evaluation Report, 3 worked examples, README) and 25% UX judging weight |
| 2026-10-31 | Skip standalone KB collection; streamline historical data schema to 10 core fields on tickets | Simplifies data curation for Member 3 and satisfies FR-03/FR-04 with a single schema |
| 2026-10-31 | Include `assignment_group`, `status`, `created_at` (FR-07) and `feedback_status` (FR-06) in ticket schema | Explicitly satisfies FR-06 reviewer feedback tracking and FR-07 multi-facet queue filtering |
| 2026-10-31 | App layer talks to SQLite through `database.py` (stdlib `sqlite3`, no ORM, no HTTP tier) | Single-tier Streamlit design from `system_design.md`; removes a network hop and ~30 minutes of setup risk on a 6-hour clock |
| 2026-10-31 | Taxonomy, priority and assignment-group options are read from the 200-record corpus at startup, never hardcoded | The corpus uses `Hardware & Endpoints` / `Software & Cloud Applications` / `Security & Compliance`, which differ from the 5 category names in `system_design.md` §5; deriving from data prevents silent UI/LLM drift |
| 2026-10-31 | KPI cards compute from SQLite on every rerun; no hardcoded accuracy/deflection percentages anywhere | Judges ask how a number was measured; a live query is defensible, a placeholder is not |
| 2026-10-31 | `app.py` imports `rag_service.py` optionally and falls back to manual triage with a visible banner | The RAG module is built in a separate lane; the demo path must never break while it is missing |
| 2026-10-31 | `system_design.md` §5 corrected to the corpus taxonomy (`Hardware & Endpoints`, `Software & Cloud Applications`, `Security & Compliance`); old names deleted | The RAG agent is specced from that file; emitting categories the corpus and UI do not contain would silently break filtering and retrieval labels |
| 2026-10-31 | Category → assignment-group mapping is derived from the corpus (majority group) instead of a hardcoded dict | One less place to drift if the dataset is re-curated; falls back to the canonical mapping if the corpus is unreadable |
| 2026-10-31 | Canonical corpus lives at the repo root (`historical_incidents_200.json/.csv`); duplicate copies under `hackathon/data/` deleted | One file per format, one path in every reference; `hackathon/` holds planning docs only. `rag_service.py` must default to the root path |

## Open decisions

Track unresolved choices with a deadline so they do not drift into hour 30.

| Decision | Owner | Deadline | Blocked on |
| --- | --- | --- | --- |
|  |  |  |  |
