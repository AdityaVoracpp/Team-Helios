# Demo script — Helios ITSM Assist

Target duration: 3 minutes. Every beat matches a visible screen action and one spoken line.

> **Build state this script reflects (2026-10-31):** single-tier Streamlit app, SQLite persistence,
> 12 seeded demo tickets, 200-record retrieval corpus. `rag_service.py` is **not wired yet** — the UI
> says so in a banner. Beats 4 and 5 have an explicit "RAG not ready" fallback; do not improvise AI
> output that the app does not produce.

## One-sentence pitch

> For **IT support analysts and enterprise employees** who **lose hours to manual triage, duplicate tickets and slow resolution**, **Helios ITSM Assist** delivers **pre-submission deflection, structured ticket classification and evidence-backed resolution playbooks grounded in historical incidents**, so they get **faster answers with traceable, non-hallucinated guidance**.

## Beats

| # | Time | Screen action | Spoken line | Failure fallback |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0:00-0:25 | Sidebar → **Admin (Support Workbench)**. Point at the four KPI cards (Total tickets, Open queue, Deflection rate, Useful feedback). | "Every ticket queue starts with triage. These numbers are live from SQLite — not slides." | Screenshot of the workbench |
| 2 | 0:25-1:05 | Switch to **User (Employee Center)**. Step 1: type *"VPN drops with Error 504"* + details, click **Next — auto-fill from history**. Step 2 appears with category, subcategory, priority, assignment group and affected service pre-filled, with a confidence score. | "Before the employee submits anything, Helios reads the ticket against 200 historical incidents and drafts the triage fields for them." | Pre-typed draft ready in a second tab |
| 3 | 1:05-1:50 | Change one pre-filled field (e.g. set Category to `Hardware & Endpoints`) and point out the assignment group re-derives itself. Click **Submit incident anyway** → switch to **Admin** → filter Category = the one you picked → open the new ticket. | "Every field is editable — the analyst still owns the decision, and the audit trail keeps both the suggestion and the override." | Seeded ticket `INC000001` |
| 4 | 1:50-2:30 | On the ticket: click 👍 **Useful**, then open **🔍 AI audit & explainability** and show the JSON trace. *(If `rag_service.py` has landed: click **Generate resolution playbook** first and show steps + citations.)* | "Every decision is traceable: what came in, what the system predicted, which precedents it used, and what the analyst decided." | Pre-cached ticket detail view |
| 5 | 2:30-3:00 | Wrap-up slide: architecture, corpus size, honest status. | "Helios: classify, deflect, resolve, and trace — grounded in 200 historical incidents." | Summary slide |

## Numbers to say out loud (verified — quote these)

- **Corpus:** 200 historical incidents, 5 categories × 40 records, 14 fields per record.
- **Demo queue:** 12 seeded tickets — 10 open, 2 resolved — derived from the corpus.
- **App-layer verification:** 6/6 end-to-end checks pass (`python tests/test_smoke.py`).
- **Subcategory caveat:** subcategory is constant within each category in this corpus, so it is *not* a
  meaningful accuracy win — say "category accuracy", never "taxonomy accuracy".

## Numbers you may NOT quote yet (unmeasured)

Do not put these on a slide until the RAG lane is wired and an evaluation run exists:

- Classification accuracy % and deflection % — measure on a held-out slice, record the method.
- RAG latency per recommendation and cost per run.
- Any "MTTR reduction" claim — there is no telemetry to support one.

## Setup checklist before walking up

- [ ] `python seed_db.py` run, then `streamlit run app.py` — app open at `http://localhost:8501`
- [ ] Persona left on **Admin** with the queue visible
- [ ] Wi-Fi on (RAG beats need the API) and key present in `.env`
- [ ] Backup video open in a media player, playing off disk
- [ ] Browser zoom 110%, terminal hidden

## Known gaps to state honestly if asked

- `rag_service.py` (classification, hybrid retrieval, playbook synthesis) is built separately and may be absent — the app then shows a manual-triage banner and still works end to end.
- No auth, two personas via a selector — a deliberate scope decision.
- SQLite is local-only; nothing is deployed yet.
