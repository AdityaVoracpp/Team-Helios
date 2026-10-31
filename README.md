# Helios ITSM Assist

> For **enterprise IT support analysts and employees** overwhelmed by **manual triage, duplicate tickets, and slow resolution**, **Helios ITSM Assist** provides **real-time pre-submission deflection, AI classification, and evidence-backed resolution playbooks grounded in historical incidents** so they get **faster answers, resolved duplicates, and traceable guidance with explicit low-confidence fallbacks**.

---

## Current Status (Draft & Active Build)
- **Status:** **Sprint 0 Complete | Sprint 1 (Core Build) In Progress**
- **App layer: DONE** — `app.py` (both personas, queue, feedback, audit) + `database.py` (SQLite CRUD) + `seed_db.py` (demo data). Verified by `python tests/test_smoke.py`.
- **RAG layer: IN PROGRESS** — `rag_service.py` is built separately; until it lands the app runs in a clearly-labelled manual-triage mode.
- **Dataset:** 200 synthetic enterprise IT incident records generated and validated under [`historical_incidents_200.json`](historical_incidents_200.json).
- **Core Architecture Locked:** Single-tier Python application with **Streamlit** (front-end & app layer), **SQLite** (local persistent database), **Hybrid Retrieval** (BM25 + Dense Vector Similarity), and **OpenAI API** (structured output).
- **Subsystem Division:** Main UI & Database layer integrated with an isolated **RAG Agent Service** (`rag_service.py`).

---

## Problem
Enterprise IT support systems receive massive volumes of repetitive tickets involving VPN drops, SSO authentication loops, application errors, and hardware failures. 

Manual categorization and duplicate search consumes over 60% of tier-1 support handling time, leading to high MTTR (Mean Time to Resolution) and inconsistent fixes. Existing chatbot solutions frequently hallucinate ungrounded instructions or fail to detect active duplicate incidents before users file tickets.

---

## What It Does

Helios ITSM Assist provides a dual-persona ServiceNow-inspired experience tailored for both end-users and IT support personnel:

### 1. Employee Center (`User` Persona — Self-Service)
- **Intake with Live AI Auto-fill (FR-01):** As employees describe their issue, the AI automatically suggests Category, Subcategory, Urgency, and Priority with an explicit confidence score.
- **Contextual Search & Pre-Submission Deflection (FR-02):** Before submission, a real-time radar scans historical incidents and active major outages. If a verified fix or workaround exists, it is displayed immediately. If the user clicks *"This Solved My Problem"*, the ticket is deflected pre-submission, saving IT capacity.

### 2. Support Operations Workbench (`Admin` Persona — Analyst & Triage)
- **Operational KPI Dashboard:** Every card is computed live from SQLite (total tickets, open queue, deflection rate, share of AI suggestions marked useful) — no hardcoded percentages.
- **Filterable Incident Queue (FR-07):** Multi-faceted filtering across Category, Priority (`P1` to `P4`), Status (`New`, `In Progress`, `Resolved`), Affected Service, and Assignment Group.
- **Intelligent Resolution Workbench (FR-03 & FR-04):** Synthesizes step-by-step resolution playbooks grounded directly in resolved historical cases, complete with expandable citation cards showing source ticket IDs (`INC00xxxx`), similarity scores, and verbatim excerpts.
- **Confidence Guardrail & Fallback (FR-05):** If confidence is $< 70\%$ or physical hardware damage is detected (e.g., coffee spill near USB ports), automated software resolution is suppressed. The system displays an amber warning and routes to Tier 2 escalation without hallucination.
- **Analyst Feedback Loop (FR-06):** One-click buttons (**Useful** 👍, **Incorrect** 👎, **Unresolved** ❓) allow the reviewer to evaluate the AI's recommendation, immediately updating SQLite and retraining cues.
- **Audit & Explainability Inspector (FR-08):** In-app expandable JSON viewer capturing raw input, taxonomy predictions, retrieved precedent IDs, prompt/completion metadata, and reviewer decisions.

---

## What the AI Does

1. **Classification (FR-01):** Analyzes ticket text against a structured ITIL enterprise taxonomy using strict JSON schema validation.
2. **Hybrid Precedent Retrieval (FR-02):** Combines lexical BM25 search (for exact error codes like `Error 504`, `Cisco AnyConnect`, `Okta Verify`) with dense semantic vector embeddings scored via rank fusion.
3. **Playbook Synthesis & Citations (FR-03 & FR-04):** Prompts the LLM with the active incident plus top resolved precedent excerpts to generate an ordered, 3-step action checklist with source citations.
4. **Guardrail Decision (FR-05):** Automatically suppresses resolution if top precedent similarity is below 70%, outputting an escalation notice.
5. **Fallback:** If API connectivity fails or times out, the app safely defaults to human escalation without blocking the UI.

---

## Real vs. Mocked (Judging Disclosure)

| Capability | Status | Implementation Details |
| :--- | :--- | :--- |
| **Ticket Database** | **REAL** | SQLite database (`app.db`) initialized and persisted locally. |
| **Historical Precedents** | **REAL** | 200 curated, realistic enterprise IT incidents with symptoms, resolutions, and notes in `historical_incidents_200.json`. |
| **Hybrid Retrieval** | **REAL** | In-memory BM25 index + dense vector cosine similarity over the 200 historical incidents. |
| **LLM Classification & RAG** | **PENDING** | `rag_service.py` (classification, hybrid retrieval, playbook synthesis) is owned by the RAG lane. The app imports it opportunistically and degrades to manual triage when it is absent — the banner in the UI says which mode is active. |
| **Feedback & Audit Trail** | **REAL** | Real-time updates to SQLite records and live JSON inspector. |
| **User Authentication / RBAC** | **MOCKED** | Security/auth is omitted to maximize hackathon time on core AI capabilities. A simple profile selector switches between `User` and `Admin` personas. |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        STREAMLIT WEB APPLICATION                       │
│                        (Single Python Process)                         │
│  ┌─────────────────────────────┐     ┌──────────────────────────────┐  │
│  │    User Persona (Portal)    │     │   Admin Persona (Workbench)  │  │
│  │ - Intake + Live AI Autofill │     │ - KPI Dashboard & Queue (FR07)│  │
│  │ - Pre-submission Deflection │     │ - RAG Playbook & Citations   │  │
│  └──────────────┬──────────────┘     │ - Fallback & Feedback (FR06) │  │
│                 │                    │ - Audit Inspector (FR08)     │  │
│                 │                    └──────────────┬───────────────┘  │
└─────────────────┼───────────────────────────────────┼──────────────────┘
                  │                                   │
┌─────────────────▼───────────────────────────────────▼──────────────────┐
│                          LOCAL STORAGE (SQLite)                        │
│                 Tickets Table (Metadata, Status, Audit Data)           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                       RAG & AI SERVICE MODULE                          │
│  - Hybrid Search Engine (BM25 + FAISS / Cosine Semantic Similarity)   │
│  - 200 Seed Incidents Corpus (historical_incidents_200) │
│  - OpenAI Structured Output (Classification, Resolution Playbooks)    │
│  - Confidence Guardrail Gatekeeper (< 70% Fallback Trigger)            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## How to Run Locally

### 1. Prerequisites
- Python 3.10–3.12 (verified on 3.12.10)
- An OpenAI API key — only needed once `rag_service.py` lands; the app layer runs without it

### 2. Setup & Installation
```bash
# Clone the repository
git clone https://github.com/AdityaVoraCpp/Team-Helios.git
cd Team-Helios

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure your environment
cp .env.example .env
# Edit .env and set your OPENAI_API_KEY
```

### 3. Seed demo data and run
```bash
python seed_db.py          # wipes app.db and loads a 12-ticket demo queue
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

Use the **Admin (Support Workbench)** persona to see the seeded queue. `Reset demo data` in the sidebar empties the table; `python seed_db.py` restores it.

### 4. Verify the app layer
```bash
python tests/test_smoke.py   # intake -> submit -> queue -> feedback -> reset
```
The test drives the real Streamlit script through `st.testing.AppTest` against a temporary database, so it never touches your demo data.

---

## Technical Stack

| Layer | Choice | Why |
| :--- | :--- | :--- |
| **Application & UI** | **Streamlit** | Fast, reactive Python web UI; zero build tools or NodeJS dependencies needed; immediate stateful controls. |
| **Database** | **SQLite** | Zero-latency, zero-configuration local ACID storage; stores live demo tickets and audit traces. |
| **Retrieval Engine** | **BM25 + FAISS / NumPy Cosine** | Hybrid search combining exact keyword/error code matching with dense semantic similarity. |
| **AI / LLM** | **OpenAI API (GPT-4o-mini)** | Strict JSON schema output via Pydantic; latency target < 2 s, to be measured once the RAG lane lands. |
| **Data Corpus** | **200 Curated Incidents** | 5 categories × 40 records: Network & Connectivity, Identity & Access, Hardware & Endpoints, Software & Cloud Applications, Security & Compliance. Subcategory is constant per category, so it is reported but not claimed as a prediction win. |

---

## Project Documentation & Hackathon Governance
Detailed hackathon governance and evaluation documents live under [`hackathon/`](hackathon/):
- [`hackathon/RULES.md`](hackathon/RULES.md) — Official brief and judging alignment
- [`hackathon/DECISIONS.md`](hackathon/DECISIONS.md) — Architecture and design log
- [`hackathon/TASKS.md`](hackathon/TASKS.md) — Task board and completion status
- [`hackathon/DEMO-SCRIPT.md`](hackathon/DEMO-SCRIPT.md) — 3-minute pitch and demo narration
