# Helios ITSM Assist — Streamlined AI Handover & Implementation Specification
**Project:** Helios ITSM Assist (`Team-Helios`)  
**Hackathon:** HCLTech | Future Ready AI Engineer Hackathon  
**Use Case:** Intelligent IT Ticket Analysis and Resolution Assistant (Enterprise IT / Service Management)  
**Architecture:** Single-Tier Python Application (Streamlit + SQLite + OpenAI API + Separate RAG Service Module)  
**Execution Mode:** Main App Agent + Isolated RAG Service Agent

---

## 1. Executive Context & System Framing

### 1.1 The One-Sentence Framing
> *"For enterprise IT support and employees overwhelmed by manual triage, duplicate tickets, and slow resolution, **Helios ITSM Assist** provides real-time pre-submission deflection, AI classification, and evidence-backed resolution playbooks grounded in historical incidents, delivering instant answers, 30%+ deflection, and drastically reduced MTTR with zero-hallucination guardrails."*

### 1.2 Core Design Principles (Streamlined)
1. **No FastAPI / No Multi-Tier Overhead:** Everything runs in a cohesive, clean Python stack. Streamlit delivers the front-end and application logic directly on port 8501.
2. **Modular RAG Agent Subsystem:** The RAG and AI logic is encapsulated in an isolated module: `rag_service.py`. This module is built by a dedicated RAG Agent and called directly by the Streamlit app.
3. **Database:** Standard **SQLite** (`app.db`) accessed directly via Python (`sqlite3` / `pydantic`). Zero network latency, zero setup risk.
4. **Pre-Generated Dataset:** 200 realistic, curated enterprise incident records already live at [`historical_incidents_200.json`](historical_incidents_200.json).
5. **No Auth / 2 Personas:** Security/auth is omitted to keep 100% focus on the AI assistant capabilities. A simple profile selector in the top bar / sidebar toggles between:
   - **`User` (Employee Self-Service):** Intake form, AI auto-fill, pre-submission deflection radar.
   - **`Admin` (Admin + Resolver Combined):** KPI metrics, filterable incident queue (FR-07), resolution workbench (FR-03/04), low-confidence fallback (FR-05), feedback bar (FR-06), and audit log viewer (FR-08).
6. **Simplified Audit Trace:** No separate database table. Audit data is stored as a JSON object directly on the ticket record and viewed via an in-app expander (`st.json`).
7. **Evaluation Deferred to Last:** Core functional demo flow is built and verified first. Evaluation benchmark and reporting are completed only after the end-to-end application works cleanly.

---

## 2. Canonical Mapping of the 8 Functional Requirements

| Req ID | Capability | Streamlined Implementation | Demo Proof Point |
| :--- | :--- | :--- | :--- |
| **FR-01** | **Ticket Classification** | LLM structured output returning Category, Subcategory, Urgency, Priority (`P1`–`P4`), and confidence score (0–100%). | Auto-fill in the User intake form; confidence pill in Admin view. |
| **FR-02** | **Duplicate & Similarity Detection** | Hybrid search (FAISS / dense vector cosine + BM25 keyword matching) across historical tickets. | **Pre-submission deflection radar** on User view showing matching resolved issues; ranked duplicates in Admin queue. |
| **FR-03** | **Resolution Recommendation** | RAG prompt synthesizing proven `action_steps` and `resolution_notes` from top-ranked resolved precedents into an ordered playbook. | Step-by-step resolution checklist with "Apply Fix to Ticket" button. |
| **FR-04** | **Evidence & Traceability** | Recommendation links each action step to source ticket IDs (`INC00xxxx`), similarity score, and verbatim excerpt. | Expandable citation cards showing the exact precedent text. |
| **FR-05** | **Confidence & Fallback** | Hard threshold: If top similarity score or LLM confidence $< 70\%$, flag as `LOW_CONFIDENCE`. Suppress auto-resolution and show amber alert: *"Requires Tier 2 Escalation / Physical Inspection"*. | Ambiguous / hardware damage ticket (coffee spill) safely routed with zero hallucination. |
| **FR-06** | **Analyst Feedback** | One-click action buttons on Admin workbench: **"Useful"** (thumbs up), **"Incorrect"** (thumbs down), **"Unresolved"**. Updates `feedback_status` & `feedback_notes` in SQLite. | Admin clicks "Useful", status changes live in DB and queue. |
| **FR-07** | **Search & Filtering** | Sidebar / table filters for `category`, `priority`, `status`, `affected_service`, `assignment_group`, and `date`. | Admin filters queue to "Network Operations" + "P2 High". |
| **FR-08** | **Audit-Friendly Output** | Direct JSON field on ticket storing raw input, predicted taxonomy, retrieved IDs, prompt/response trace, and reviewer action. | "🔍 AI Audit & Explainability" expander in Streamlit displaying full JSON trace. |

---

## 3. Dataset Specification (`historical_incidents_200.json`)

The dataset contains 200 rich, realistic enterprise tickets with this exact 14-field schema:
```json
{
  "id": "INC002491",
  "title": "Cisco AnyConnect VPN disconnected with Error 504 Gateway Timeout",
  "description": "User unable to connect to internal network from home. Cisco AnyConnect client fails at handshake with Error 504. Wi-Fi is functional.",
  "symptoms": [
    "Cisco AnyConnect handshake failure",
    "Error 504 Gateway Timeout",
    "Internal resources unreachable"
  ],
  "category": "Network & Connectivity",
  "subcategory": "VPN Client",
  "priority": "P2 - High",
  "affected_service": "Cisco AnyConnect",
  "assignment_group": "Network Operations",
  "status": "Resolved",
  "created_at": "2026-10-01T08:00:00.000Z",
  "action_steps": [
    "Run 'ipconfig /flushdns' in elevated Command Prompt",
    "Re-install corrupted TAP virtual network adapter driver",
    "Re-sync root certificates and restart AnyConnect service"
  ],
  "resolution_notes": "Flushed local DNS cache and restored corrupted TAP network adapter driver.",
  "feedback_status": "useful",
  "feedback_notes": "Verified resolution for remote employee VPN issues."
}
```

---

## 3.1 Canonical taxonomy (source of truth: the corpus itself)

The 200 records collapse to five categories, and the subcategory is **constant within each category** — worth knowing before any accuracy claim, because "subcategory" carries no discriminative signal in this dataset.

| Category (40 records each) | Subcategory (constant) | Default assignment group | Priority mix (P1/P2/P3/P4) |
| :--- | :--- | :--- | :--- |
| `Network & Connectivity` | VPN Client | Network Operations | 4 / 14 / 19 / 3 |
| `Identity & Access` | Single Sign-On (SSO) | Identity & Access Management | 7 / 18 / 13 / 2 |
| `Hardware & Endpoints` | Workstation Peripherals | Desktop & End User Support | 2 / 17 / 19 / 2 |
| `Software & Cloud Applications` | Email & Collaboration | Enterprise Application Support | 4 / 17 / 15 / 4 |
| `Security & Compliance` | Endpoint Protection | Security Operations Center | 13 / 14 / 10 / 3 |

The Streamlit app reads this list from `historical_incidents_200.json` at startup (`load_taxonomy()` in `app.py`) rather than hardcoding it, so the UI cannot drift from the corpus. `rag_service.py` must emit exactly these strings.

---

## 4. Contract for the Separate RAG Agent (`rag_service.py`)

The main Streamlit application communicates with the RAG subsystem via a clean, self-contained Python file named `rag_service.py`.

### 4.1 Interface Specification

```python
# rag_service.py
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ClassificationResult(BaseModel):
    category: str
    subcategory: str
    priority: str
    urgency: str
    confidence_score: float  # 0.0 to 1.0
    reasoning: str

class SimilarTicket(BaseModel):
    id: str
    title: str
    similarity_score: float  # 0.0 to 1.0
    status: str
    resolution_summary: str
    quick_workaround: str

class DeflectionResult(BaseModel):
    deflection_suggested: bool
    similar_tickets: List[SimilarTicket]

class Citation(BaseModel):
    ticket_id: str
    similarity_score: float
    excerpt: str

class PlaybookStep(BaseModel):
    step_number: int
    action: str
    rationale: str
    source_citation: Citation

class ResolutionResult(BaseModel):
    is_low_confidence: bool
    confidence_score: float
    fallback_reason: Optional[str] = None
    escalation_group: Optional[str] = None
    playbook_steps: List[PlaybookStep] = []
    summary_notes: str
    audit_trace: Dict[str, Any]  # captures prompt info, candidate IDs, raw response

class RAGService:
    def __init__(self, data_path: str = "historical_incidents_200.json"):
        """Loads historical incidents and initializes BM25 + Vector embedding index."""
        ...

    def classify_ticket(self, title: str, description: str, affected_service: Optional[str] = None) -> ClassificationResult:
        """FR-01: Predicts taxonomy and confidence score."""
        ...

    def find_similar_and_deflect(self, title: str, description: str, affected_service: Optional[str] = None, top_k: int = 3) -> DeflectionResult:
        """FR-02: Pre-submission deflection radar."""
        ...

    def recommend_resolution(self, ticket_dict: Dict[str, Any], top_k: int = 3) -> ResolutionResult:
        """FR-03, FR-04, FR-05: Synthesizes resolution playbook with citations and <70% fallback guardrail."""
        ...
```

---

## 5. Copy-Paste Instructions for the Separate RAG Agent

You can give the prompt below directly to the agent handling the RAG subsystem:

```markdown
# Task: Build `rag_service.py` for Helios ITSM Assist

You are building the AI and Retrieval-Augmented Generation (RAG) service module for **Helios ITSM Assist**, an enterprise IT Ticket Assistant for a hackathon.

### 1. Your Goal
Implement a single, self-contained Python file `rag_service.py` that loads historical enterprise IT incidents, indexes them using hybrid retrieval, and interacts with OpenAI API using structured outputs.

### 2. Historical Incident Corpus
- File location: `historical_incidents_200.json`
- Contains 200 resolved tickets with fields: `id`, `title`, `description`, `symptoms`, `category`, `subcategory`, `priority`, `affected_service`, `action_steps`, `resolution_notes`.

### 3. Required Methods in `RAGService`

1. **`__init__(self, data_path: str)`**:
   - Load the 200 incidents from `data_path`.
   - Build a **BM25** index (using `rank-bm25`) over `title + description + " ".join(symptoms) + affected_service`.
   - Build a dense vector cache using OpenAI `text-embedding-3-small` (or normalized numpy cosine vectors with an on-disk cache `data/embeddings_cache.pkl` so you only embed once!).

2. **`classify_ticket(title: str, description: str, affected_service: str = None) -> ClassificationResult`**:
   - Classify into one of these 5 categories — **use these exact strings, they are the ones present in the corpus and the ones the UI renders**:
     `Network & Connectivity`, `Identity & Access`, `Hardware & Endpoints`, `Software & Cloud Applications`, `Security & Compliance`.
     (An earlier draft of this spec said `Hardware` / `Cloud & Infrastructure` / `Software & Applications`; those names do not exist in `historical_incidents_200.json` and must not be emitted.)
   - Return `category`, `subcategory`, `priority` (`P1` to `P4`), `urgency`, `confidence_score` (0.0 to 1.0), and `reasoning`.
   - Use OpenAI client with Pydantic structured output (`client.beta.chat.completions.parse` or schema function calling).

3. **`find_similar_and_deflect(title: str, description: str, affected_service: str = None, top_k: int = 3) -> DeflectionResult`**:
   - Perform hybrid search: combined score = $0.5 \times \text{Vector} + 0.3 \times \text{BM25} + 0.2 \times \text{ExactServiceMatch}$.
   - Return top `top_k` matches with `id`, `title`, `similarity_score`, `status`, `resolution_summary`, and a short `quick_workaround` extracted from `action_steps[0]`.
   - Set `deflection_suggested = True` if the top similarity score is $\ge 0.75$.

4. **`recommend_resolution(ticket_dict: dict, top_k: int = 3) -> ResolutionResult`**:
   - Retrieve top historical matches.
   - **Guardrail Check (FR-05):** If top similarity $< 0.70$ or if the user description indicates physical damage (e.g. liquid spill, fire, hardware failure), trigger fallback:
     - `is_low_confidence = True`
     - `confidence_score = float (< 0.70)`
     - `fallback_reason = "Low precedent confidence (< 70%) or physical hazard. Hardware depot escalation required."`
     - `escalation_group = "Tier 2 Hardware Support"`
     - `playbook_steps = []`
   - If confidence $\ge 0.70$:
     - Prompt LLM with the ticket details and the retrieved candidate tickets (their `action_steps` and `resolution_notes`).
     - LLM synthesizes an ordered 2-4 step playbook where each step cites the exact `ticket_id`, similarity score, and excerpt.
   - Include `audit_trace` containing the prompt metadata, retrieved IDs, and timestamp.

### 4. Constraints & Reliability
- Do not raise unhandled exceptions: wrap LLM calls in `try/except` with a safe fallback response if network fails.
- Fast execution: use `gpt-4o-mini` for speed (< 2s latency).
- Standalone test block: Include `if __name__ == "__main__":` demonstrating the 3 test cases:
  1. VPN Error 504 (Outage deflection).
  2. Okta SSO Loop (Grounded RAG resolution with citations).
  3. Coffee spill on laptop (Guardrail $< 70\%$ fallback).
```

---

## 6. Main Application Implementation (`app.py` & `database.py`)

### 6.1 Database Setup (`database.py`)
- SQLite database (`app.db`) with a simple `tickets` table:
  - Columns: `id`, `title`, `description`, `category`, `subcategory`, `priority`, `affected_service`, `assignment_group`, `status`, `created_at`, `action_steps` (JSON), `resolution_notes`, `feedback_status`, `feedback_notes`, `audit_data` (JSON).
- Helper functions: `init_db()`, `create_ticket(...)`, `get_all_tickets(...)`, `get_ticket(id)`, `update_feedback(id, status, notes)`.

### 6.2 Streamlit User Interface (`app.py`)
1. **Header / Profile Bar**:
   - Display: *"Helios ITSM Assist | Enterprise IT Intelligence"*
   - Persona Selector: `st.selectbox("Select Active Persona", ["User (Employee Center)", "Admin (Support Workbench)"])`
2. **If Persona == `User (Employee Center)`**:
   - Ticket intake form: Short description, detailed description, affected service.
   - *"Analyze Issue"* button: calls `rag_service.classify_ticket(...)` and fills suggested category/priority pills.
   - Real-time Deflection Radar: calls `rag_service.find_similar_and_deflect(...)`. Shows matching resolved issue + workaround.
   - Buttons: *"This Solved My Problem"* (deflects ticket) vs. *"Submit Incident Anyway"* (inserts into `tickets` table).
3. **If Persona == `Admin (Support Workbench)`**:
   - KPI metric cards: Total Tickets, Open Queue, Deflection Rate, Useful-Feedback Share — all computed live from SQLite via `database.get_stats()`. No hardcoded percentages anywhere in the UI.
   - Incident Queue with faceted filters: Category, Priority, Status, Assignment Group.
   - Selected ticket details + **AI Resolution Assistant**:
     - Calls `rag_service.recommend_resolution(...)`.
     - Displays ordered resolution steps with clickable source citation badges.
     - Displays Amber Alert if `is_low_confidence == True`.
     - Feedback buttons: 👍 **Useful** | 👎 **Incorrect** | ❓ **Unresolved** (updates SQLite).
     - Expander: `with st.expander("🔍 AI Audit & Explainability"): st.json(ticket["audit_data"])`.

