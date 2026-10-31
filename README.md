# Helios ITSM Assist

Helios ITSM Assist is a Streamlit application for employee IT issue intake and support analyst triage. It classifies reported issues, searches historical incidents for relevant precedents, and presents evidence-backed resolution guidance with confidence and safety guardrails.

> **Live Streamlit demo:** Deployment URL pending. Share the deployed app URL to add it here.

## What it does

- **Employee Center:** Collects an issue in a two-step flow and suggests category, subcategory, priority, assignment group, and affected service for review before submission.
- **Historical incident search:** Uses FAISS dense retrieval, BM25 keyword search, and exact affected-service matching over the incident corpus.
- **Deflection radar:** Shows relevant resolved incidents when the best match meets the 0.75 similarity threshold. Employees can use a historical resolution or submit an incident for analyst review.
- **Analyst workbench:** Provides a filterable ticket queue, ticket details, grounded resolution recommendations, citations, feedback controls, and an audit trace.
- **Confidence and safety guardrails:** Recommendations below 0.70 confidence fall back to human support. Physical damage and other safety-sensitive cases are escalated without troubleshooting instructions.
- **SQLite persistence:** Stores submitted tickets, resolution and feedback data, and audit information locally.

The application suggests triage values and troubleshooting actions; a person remains responsible for reviewing them. It does not perform autonomous remediation or privileged system changes. The persona selector is for the demo and is not authentication or role-based access control.

## How the RAG flow works

1. The user describes an IT issue and optionally names the affected service.
2. LangChain calls OpenAI for structured ticket classification and embeddings.
3. Retrieval combines normalized FAISS cosine similarity, normalized BM25 scores, and exact service matching using weights of **0.50**, **0.30**, and **0.20**. The top three incidents are considered.
4. The deflection radar suggests self-service only when the top match scores at least **0.75**.
5. For analyst recommendations, the service uses resolved historical incidents as its evidence. Generated actions must cite retrieved source tickets and excerpts. If evidence is insufficient, confidence is below **0.70**, or the issue is safety-sensitive, the service returns a human-support fallback.

## Architecture

```text
Streamlit UI (app.py)
  ├── Employee intake and analyst workbench
  ├── RAG service (hackathon/rag_service.py)
  │     ├── OpenAI classification and embeddings via LangChain
  │     ├── FAISS + BM25 + exact-service hybrid retrieval
  │     └── Grounded recommendations, citations, guardrails, audit trace
  └── SQLite persistence (database.py)

Historical incidents (historical_incidents_200.json)
  └── Retrieval corpus; generated embeddings are cached locally
```

## Technology

| Area | Technology |
| --- | --- |
| UI and application | Python, Streamlit |
| RAG orchestration | LangChain, `langchain-openai` |
| Chat model | OpenAI `gpt-4o-mini` |
| Embeddings | OpenAI `text-embedding-3-small` |
| Retrieval | FAISS and `rank-bm25` |
| Validation | Pydantic |
| Application data | SQLite |
| Configuration | `python-dotenv` |

The historical incident file contains 200 curated records and is used as the RAG corpus. `seed_db.py` derives a small demo queue from that corpus; it does not replace or modify the source dataset.

## Run locally

### Prerequisites

- Python 3.10 or newer
- An OpenAI API key for classification, embeddings, and resolution generation

### Install and configure

From the repository root, create and activate a virtual environment, then install the project dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

On macOS or Linux, activate and copy the environment template with:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your key to `OPENAI_API_KEY` in your local `.env` file. Keep `.env` private; it is ignored by Git. The model defaults are already set in `.env.example`:

```dotenv
OPENAI_API_KEY=your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
```

### Seed the demo queue and start Streamlit

```bash
python seed_db.py
streamlit run app.py
```

Open `http://localhost:8501`. The seed command resets and populates the local SQLite ticket queue. Run it again to restore the demo queue. The first RAG startup may call the embeddings API to build the local cache; subsequent starts can reuse that cache while the corpus and embedding model remain unchanged.

## Tests

Run the existing smoke, integration, and RAG service test scripts from the repository root:

```bash
python tests/test_smoke.py
python tests/test_rag_integration.py
python hackathon/tests/test_rag_service.py
```

The RAG integration and service tests stub model calls where applicable. The running application still requires a valid OpenAI key for live AI requests.

## Project layout

```text
.
├── app.py                          # Streamlit employee and analyst interfaces
├── database.py                     # SQLite schema and ticket operations
├── seed_db.py                      # Seeds the local demo ticket queue
├── historical_incidents_200.json   # Historical RAG corpus
├── hackathon/
│   ├── rag_service.py              # Classification, retrieval, recommendations
│   └── tests/test_rag_service.py   # RAG service tests
├── tests/
│   ├── test_smoke.py
│   └── test_rag_integration.py
├── requirements.txt
└── .env.example
```

## Project documents

- [RAG design](hackathon/RAG_DESIGN.md)
- [System design](hackathon/system_design.md)
- [Hackathon rules](hackathon/RULES.md)
- [Demo script](hackathon/DEMO-SCRIPT.md)

## Security and limitations

- Never commit `.env`, API keys, or local embedding caches.
- The demo persona selector does not provide real user authentication or authorization.
- Recommendations depend on the coverage and quality of the historical incident corpus. When relevant resolved evidence is unavailable, the service should direct the user to human IT support instead of inventing a fix.
- No ticket is created outside the local application database, and no external ITSM system is modified.
