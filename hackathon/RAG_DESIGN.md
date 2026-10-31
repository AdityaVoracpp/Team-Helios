# Helios ITSM Assist --- RAG Design Specification

**Project:** Helios ITSM Assist (`Team-Helios`)\
**Hackathon:** HCLTech --- Future Ready AI Engineer Hackathon\
**Use case:** Intelligent IT Ticket Analysis and Resolution Assistant\
**Primary module:** `rag_service.py`\
**Architecture:** Streamlit + Python + SQLite + OpenAI API + isolated
RAG service module

------------------------------------------------------------------------

## 1. Purpose and scope

The RAG subsystem understands an incoming IT issue, retrieves relevant
historical incidents, and recommends a resolution only when the
historical evidence is sufficiently reliable.

The Streamlit application calls the RAG subsystem directly through
`rag_service.py`. The RAG module owns corpus loading, classification,
indexing, retrieval, evidence checks, grounded generation, confidence
guardrails, citations, and its AI audit trace.

### Responsibilities

1.  Load and validate the historical incident corpus.
2.  Prepare searchable text for every incident.
3.  Build and reuse dense-vector and BM25 indexes.
4.  Classify a new issue into the agreed incident taxonomy.
5.  Retrieve and rank the top three similar incidents.
6.  Decide whether a deflection suggestion is appropriate.
7.  Generate an evidence-grounded resolution playbook from suitable
    resolved incidents.
8.  Return a safe fallback when evidence is insufficient, unsafe,
    contradictory, or unavailable.
9.  Return source references and audit metadata to the application.

### Out of scope for this module

-   Streamlit pages, widgets, navigation, and styling.
-   Creating or managing the SQLite application database.
-   Creating, submitting, closing, or updating tickets.
-   Executing commands or changing enterprise systems.
-   Claiming a suggested fix has been applied or that a diagnosis is
    certain.

The main application owns UI and database operations. `rag_service.py`
returns structured results and does not directly create or update
tickets.

------------------------------------------------------------------------

## 2. Inputs and historical data

### 2.1 Canonical corpus

The system design specifies this dataset:

`hackathon/data/historical_incidents_200.json`

It contains 200 curated, realistic enterprise incident records. This
JSON corpus is the source used to build the RAG indexes.

### 2.2 Incident fields

The system design calls this an exact 14-field schema, but its example
and listed field names contain 16 fields. Inspect the actual JSON file
and preserve all fields found there; do not drop fields just to force
the count to 14.

  -----------------------------------------------------------------------
  Field                   Type                    RAG usage
  ----------------------- ----------------------- -----------------------
  `id`                    string                  Stable incident ID for
                                                  results, citations, and
                                                  audit

  `title`                 string                  Searchable issue
                                                  summary

  `description`           string                  Searchable problem
                                                  description

  `symptoms`              list of strings         Searchable symptom
                                                  phrases

  `category`              string                  Classification metadata

  `subcategory`           string                  Classification metadata

  `priority`              string                  Historical severity
                                                  context

  `affected_service`      string                  Searchable service and
                                                  exact-match signal

  `assignment_group`      string                  Support
                                                  ownership/escalation
                                                  context

  `status`                string                  Determines whether
                                                  record can support a
                                                  resolution

  `created_at`            ISO-8601 string         Historical context

  `action_steps`          list of strings         Main source for
                                                  playbook actions

  `resolution_notes`      string                  Supporting resolution
                                                  evidence

  `feedback_status`       string                  Quality signal,
                                                  e.g. `useful`

  `feedback_notes`        string                  Additional feedback
                                                  context
  -----------------------------------------------------------------------

Example record shape:

``` json
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

### 2.3 Incoming issue

The service receives:

-   `title`: short issue summary.
-   `description`: user's detailed explanation.
-   `affected_service`: optional service/application name.
-   `ticket_dict`: issue fields plus any classification metadata, for
    resolution recommendation.

Optional values may be absent. Validate inputs and handle missing fields
safely.

------------------------------------------------------------------------

## 3. End-to-end RAG workflow

``` text
Historical incidents JSON
          |
          v
 Load + validate records
          |
          v
 Prepare searchable text
          |
      +---+-------------------+
      |                       |
      v                       v
OpenAI embeddings          BM25 keyword index
text-embedding-3-small     rank-bm25
      |                       |
      v                       |
Dense vector index/cache       |
      |                       |
      +-----------+-----------+
                  |
                  v
          Incoming IT issue
                  |
       +----------+----------+
       |                     |
       v                     v
LLM classification     Prepare retrieval query
       |                     |
       |              Query embedding + BM25
       |                     |
       |                     v
       |              Hybrid ranking
       |                     |
       |                     v
       |              Top 3 candidates
       |                     |
       |                     v
       |              Evidence/guardrail checks
       |                     |
       +----------+----------+
                  |
          +-------+-------+
          |               |
     Evidence passes   Evidence fails,
          |            unsafe, or error
          v               |
  Grounded LLM playbook   |
          |               v
          |         Safe fallback
          +-------+-------+
                  |
                  v
       Structured result + citations
              + audit trace
                  |
                  v
          Streamlit application
```

### Processing steps

1.  Load and validate the JSON corpus.
2.  Build a searchable text representation for every incident.
3.  Build or load the dense embedding index and BM25 index.
4.  Receive the user's issue.
5.  Classify it into the fixed taxonomy.
6.  Build a retrieval query from title, description, symptoms if
    supplied, and affected service.
7.  Run dense retrieval and BM25 retrieval.
8.  Combine retrieval signals using the specified hybrid score.
9.  Return the top three similar incidents by default.
10. For resolution, check similarity, status, usable resolution
    evidence, and safety.
11. If evidence passes, ask the LLM for a short grounded playbook.
12. Validate all citations and generated actions.
13. Otherwise return a low-confidence fallback with no troubleshooting
    steps.
14. Include source IDs, score details, and processing metadata in the
    audit trace.

------------------------------------------------------------------------

## 4. Corpus preparation and indexing

### 4.1 Searchable text

Construct a normalized text string for each incident from:

`title + description + " ".join(symptoms) + affected_service`

This is the specified BM25 content and should also be used, or adapted
consistently, for dense embeddings.

Preparation rules:

-   Convert missing optional text to an empty string.
-   Join symptom strings with spaces.
-   Normalize whitespace.
-   Preserve error codes, product/service names, acronyms, and technical
    terms.
-   Keep each original incident record associated with its index
    position.
-   Do not use resolution text as the primary similarity text by
    default; retrieval should match the reported problem, not merely
    similar solution wording.

### 4.2 Dense embeddings

Use OpenAI embedding model:

`text-embedding-3-small`

Create one embedding for each historical incident's searchable text.
Embed the incoming query with the same model at query time.

Dense retrieval identifies semantically similar issues even when the
user uses different wording.

### 4.3 Dense index and cache

The system design permits normalized NumPy cosine vectors or FAISS. The
project dependencies include `faiss-cpu`; use FAISS for dense indexing
if it works reliably in the project environment.

Suggested cache path:

`hackathon/data/embeddings_cache.pkl`

Expected behavior:

-   First run: embed historical records, build index, save cache.
-   Later runs: reuse cache if it matches the current corpus and model.
-   Rebuild when corpus content/order, record IDs, or embedding model
    changes.
-   Do not call the embedding API for every Streamlit rerun.
-   Keep generated cache files out of Git unless the team explicitly
    decides otherwise.

Store cache metadata such as embedding model, record IDs/order, and a
corpus fingerprint. Do not reuse a cache solely because the file exists.

### 4.4 BM25 index

Use `rank-bm25` over tokenized searchable text:

`title + description + " ".join(symptoms) + affected_service`

BM25 is especially useful for exact error codes, application names,
product names, and technical phrases. Use a consistent tokenizer for
corpus and query. A basic lowercase tokenizer is acceptable initially,
provided meaningful technical tokens are preserved.

------------------------------------------------------------------------

## 5. Classification --- FR-01

### 5.1 Approved categories

The classifier must choose one of these five categories:

1.  `Network & Connectivity`
2.  `Identity & Access`
3.  `Hardware & Endpoints`
4.  `Software & Cloud Applications`
5.  `Security & Compliance`

These are the exact category strings in `historical_incidents_200.json`; the
Streamlit workbench filters on them, so the classifier must not emit any other
spelling.

### 5.2 Classification result

`ClassificationResult` contains:

  Field                Type     Meaning
  -------------------- -------- -------------------------------------
  `category`           string   One of the five approved categories
  `subcategory`        string   More specific issue type
  `priority`           string   Priority from `P1` to `P4`
  `urgency`            string   Urgency assessment
  `confidence_score`   float    Confidence from 0.0 to 1.0
  `reasoning`          string   Concise classification explanation

Use OpenAI structured output with Pydantic, as described in the system
design (`client.beta.chat.completions.parse` or schema-based function
calling).

### 5.3 Classification rules

-   Never return a category outside the approved taxonomy.
-   Keep priority in the `P1`--`P4` range; map to UI labels
    consistently.
-   Classification confidence is separate from retrieval similarity. A
    confident category prediction does not prove that a historical
    resolution exists.
-   Handle invalid structured output and API failure safely.
-   Do not invent technical facts that are absent from the incoming
    issue.

------------------------------------------------------------------------

## 6. Hybrid retrieval --- FR-02

### 6.1 Retrieval signals

For each incoming issue:

1.  Embed the query with `text-embedding-3-small`.
2.  Calculate dense-vector similarity.
3.  Retrieve BM25 keyword relevance.
4.  Calculate exact affected-service match.
5.  Combine the scores.
6.  Rank candidates and return the top three by default.

### 6.2 Required scoring formula

The system design specifies:

\[ `\text{Hybrid Score}`{=tex} = 0.5
`\times `{=tex}`\text{Vector Score}`{=tex} + 0.3
`\times `{=tex}`\text{BM25 Score}`{=tex} + 0.2
`\times `{=tex}`\text{Exact Service Match}`{=tex} \]

Definitions:

-   `Vector Score`: semantic similarity between query and incident
    embeddings.
-   `BM25 Score`: keyword relevance.
-   `Exact Service Match`: `1` if the supplied affected service matches
    the historical incident service, otherwise `0`.

**Important implementation detail:** Raw BM25 scores are not naturally
bounded to 0--1. Normalize BM25 scores across the candidate set (or use
another documented normalization) before applying the formula. Ensure
vector similarity is on a compatible scale. Keep component scores in the
audit trace.

### 6.3 Similar ticket result

`SimilarTicket` contains:

  -----------------------------------------------------------------------
  Field                   Type                    Meaning
  ----------------------- ----------------------- -----------------------
  `id`                    string                  Historical incident ID

  `title`                 string                  Historical incident
                                                  title

  `similarity_score`      float                   Combined hybrid score,
                                                  represented from 0.0 to
                                                  1.0

  `status`                string                  Historical incident
                                                  status

  `resolution_summary`    string                  Summary based on
                                                  historical resolution
                                                  notes

  `quick_workaround`      string                  Preview from
                                                  `action_steps[0]`, if
                                                  present
  -----------------------------------------------------------------------

Do not invent the quick workaround. If the record has no first action
step, return an empty or unavailable value.

### 6.4 Deflection threshold

Set `deflection_suggested = True` when the top hybrid similarity score
is `>= 0.75`. Otherwise set it to `False`.

Deflection is a suggestion that a historical case may help; it is not
proof that the current issue is identical or resolved. Show the
historical ticket's ID and status.

### 6.5 Status and resolution evidence

-   A `Resolved` incident with meaningful `action_steps` and/or
    `resolution_notes` may support a resolution recommendation.
-   An unresolved incident may be displayed as a similar case but must
    not be represented as a proven successful resolution.
-   Do not fabricate a resolution summary if the historical record has
    no resolution content.

------------------------------------------------------------------------

## 7. Resolution recommendation and citations --- FR-03 / FR-04

### 7.1 Evidence selection

The top three retrieval results are candidates, not automatically valid
evidence. Before generation, select only records that are:

-   Relevant to the incoming issue.
-   Preferably marked `Resolved`.
-   Populated with useful `action_steps` and/or `resolution_notes`.
-   Not contradictory in a way that prevents a safe recommendation.
-   Not dependent on unsupported privileged or destructive actions.

### 7.2 Grounded generation

When evidence is sufficient, ask the LLM to synthesize an ordered
playbook of approximately 2--4 steps.

The generation prompt must instruct the model to:

-   Use only the incoming issue and retrieved historical evidence.
-   Treat historical actions as precedents, not guaranteed fixes.
-   Never add commands, settings, causes, or diagnostic claims not
    supported by the evidence.
-   Never invent ticket IDs, excerpts, similarity scores, or citations.
-   State when evidence is incomplete.
-   Return no playbook when evidence does not support safe instructions.

Every generated step must cite a real retrieved incident and supporting
excerpt.

### 7.3 Citation model

`Citation`:

  -----------------------------------------------------------------------
  Field                   Type                    Meaning
  ----------------------- ----------------------- -----------------------
  `ticket_id`             string                  Exact source incident
                                                  ID

  `similarity_score`      float                   Score for that
                                                  retrieved incident

  `excerpt`               string                  Verbatim supporting
                                                  text from its action
                                                  steps or resolution
                                                  notes
  -----------------------------------------------------------------------

`PlaybookStep`:

  -----------------------------------------------------------------------
  Field                   Type                    Meaning
  ----------------------- ----------------------- -----------------------
  `step_number`           integer                 Position in ordered
                                                  playbook

  `action`                string                  Recommended action
                                                  grounded in evidence

  `rationale`             string                  Why the action is
                                                  relevant

  `source_citation`       Citation                Historical source
                                                  supporting the action
  -----------------------------------------------------------------------

Citation validation is mandatory:

-   `ticket_id` must exist in the retrieved candidate set.
-   `similarity_score` must be copied from that candidate.
-   `excerpt` must be present in the cited record's `action_steps` or
    `resolution_notes`.
-   Reject or remove unsupported steps.
-   Never accept plausible-looking but nonexistent citations.

### 7.4 Resolution result

`ResolutionResult` contains:

  -----------------------------------------------------------------------
  Field                   Type                    Meaning
  ----------------------- ----------------------- -----------------------
  `is_low_confidence`     bool                    Whether fallback is
                                                  required

  `confidence_score`      float                   Recommendation
                                                  confidence, 0.0--1.0

  `fallback_reason`       optional string         Why no reliable
                                                  playbook was produced

  `escalation_group`      optional string         Suggested support group
                                                  when known

  `playbook_steps`        list of PlaybookStep    Grounded steps; empty
                                                  on fallback

  `summary_notes`         string                  Concise summary or
                                                  fallback explanation

  `audit_trace`           dictionary              Retrieval,
                                                  prompt/response
                                                  metadata, IDs,
                                                  timestamp
  -----------------------------------------------------------------------

Use `Field(default_factory=list)` for Pydantic list defaults rather than
a shared mutable list default.

------------------------------------------------------------------------

## 8. Confidence guardrails and fallback --- FR-05

### 8.1 Keep the thresholds separate

  ------------------------------------------------------------------------
  Decision                                 Threshold Meaning
  --------------------- ---------------------------- ---------------------
  Deflection suggestion   Top hybrid score `>= 0.75` Show a potentially
                                                     useful historical
                                                     match

  Resolution                Top similarity `>= 0.70` Eligible to attempt
  eligibility               plus sufficient evidence grounded generation

  Final resolution                 Must be `>= 0.70` Otherwise suppress
  confidence                                         playbook and fall
                                                     back
  ------------------------------------------------------------------------

Do not confuse the `0.75` deflection threshold with the `0.70`
resolution guardrail.

### 8.2 Mandatory fallback conditions

Return low confidence and an empty `playbook_steps` list if:

1.  Top similarity is below `0.70`.
2.  Generated recommendation confidence is below `0.70`.
3.  No suitable resolved precedent has usable resolution evidence.
4.  The issue indicates physical damage or a safety-sensitive scenario,
    such as liquid spill, fire, or hardware damage.
5.  Evidence is contradictory or cannot support safe instructions.
6.  An API/network failure prevents a reliable result.
7.  Citation validation fails or generated steps are unsupported.

The system design specifically names a coffee spill on a laptop as a
guardrail test.

### 8.3 Fallback result

The fallback must:

-   Set `is_low_confidence = True`.
-   Set `playbook_steps = []`.
-   Populate `fallback_reason`.
-   Set `escalation_group` when a relevant group is known.
-   Explain that reliable historical evidence was not found, or that
    specialist inspection is required.
-   Avoid speculative troubleshooting instructions.

The system design's example fallback reason is:

`Low precedent confidence (< 70%) or physical hazard. Hardware depot escalation required.`

For the coffee-spill case, the design names `Tier 2 Hardware Support`.
Do not use that group for every issue; choose a relevant known group or
a neutral human-support recommendation.

### 8.4 Confidence is not interchangeable

High classification confidence does not imply high retrieval confidence.
High similarity does not imply a usable resolution if the matching
incident is unresolved or has no resolution notes/action steps. All
evidence and safety checks must pass.

------------------------------------------------------------------------

## 9. Audit trace and explainability --- FR-08

Every recommendation should include an `audit_trace` dictionary
sufficient to inspect the decision.

Recommended structure:

``` json
{
  "timestamp": "ISO-8601 timestamp",
  "input": {
    "title": "User issue title",
    "description": "User issue description",
    "affected_service": "Service name"
  },
  "classification": {
    "category": "Network & Connectivity",
    "subcategory": "VPN Client",
    "priority": "P2",
    "urgency": "High",
    "confidence_score": 0.91
  },
  "retrieval": {
    "embedding_model": "text-embedding-3-small",
    "top_k": 3,
    "scoring_weights": {
      "vector": 0.5,
      "bm25": 0.3,
      "exact_service_match": 0.2
    },
    "candidates": [
      {
        "ticket_id": "INC002491",
        "vector_score": 0.88,
        "bm25_score": 0.79,
        "exact_service_match": 1,
        "hybrid_score": 0.86
      }
    ]
  },
  "guardrail": {
    "threshold": 0.70,
    "is_low_confidence": false,
    "fallback_reason": null
  },
  "generation": {
    "model": "gpt-4o-mini",
    "source_ticket_ids": ["INC002491"]
  }
}
```

This is a structural example only. Runtime values must be computed from
actual processing; never hardcode example IDs or scores.

Audit guidance:

-   Record model names, thresholds, retrieved IDs, score components, and
    timestamp.
-   Record concise prompt metadata or a prompt/version identifier.
-   Never store API keys or secrets.
-   Avoid retaining unnecessary sensitive user data.
-   If raw model output is retained for debugging, ensure it does not
    expose secrets.
-   The main application stores audit JSON on the ticket record and
    displays it in the Streamlit audit expander, as described in the
    system design.

------------------------------------------------------------------------

## 10. Public Python interface

The Streamlit app should call the service without knowing its internal
indexing implementation.

### 10.1 Pydantic models

``` python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    category: str
    subcategory: str
    priority: str
    urgency: str
    confidence_score: float
    reasoning: str


class SimilarTicket(BaseModel):
    id: str
    title: str
    similarity_score: float
    status: str
    resolution_summary: str
    quick_workaround: str


class DeflectionResult(BaseModel):
    deflection_suggested: bool
    similar_tickets: List[SimilarTicket] = Field(default_factory=list)


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
    playbook_steps: List[PlaybookStep] = Field(default_factory=list)
    summary_notes: str
    audit_trace: Dict[str, Any] = Field(default_factory=dict)
```

### 10.2 Required class and methods

``` python
class RAGService:
    def __init__(
        self,
        data_path: str = "hackathon/data/historical_incidents_200.json"
    ):
        """Load records and initialize/load BM25 and dense indexes."""

    def classify_ticket(
        self,
        title: str,
        description: str,
        affected_service: Optional[str] = None
    ) -> ClassificationResult:
        """FR-01: Predict issue taxonomy and confidence."""

    def find_similar_and_deflect(
        self,
        title: str,
        description: str,
        affected_service: Optional[str] = None,
        top_k: int = 3
    ) -> DeflectionResult:
        """FR-02: Retrieve and rank similar incidents."""

    def recommend_resolution(
        self,
        ticket_dict: Dict[str, Any],
        top_k: int = 3
    ) -> ResolutionResult:
        """FR-03/04/05: Return a grounded playbook or safe fallback."""
```

### 10.3 Method boundaries

-   `__init__`: load/validate corpus and initialize indexes; do not
    rebuild embeddings per query.
-   `classify_ticket`: classification only.
-   `find_similar_and_deflect`: similar incidents and deflection
    decision; no ticket creation.
-   `recommend_resolution`: retrieval, evidence checks, guardrails,
    generation, citation validation, and audit trace.
-   Expected API/network errors should be handled and returned as
    controlled results rather than crashing Streamlit.

Suggested private helpers:

-   `_load_incidents()`
-   `_prepare_incident_text(record)`
-   `_load_or_build_embeddings()`
-   `_build_bm25_index()`
-   `_embed_query(text)`
-   `_hybrid_search(query, affected_service, top_k)`
-   `_check_resolution_evidence(records)`
-   `_check_guardrails(...)`
-   `_generate_playbook(...)`
-   `_validate_citations(...)`
-   `_build_audit_trace(...)`

------------------------------------------------------------------------

## 11. Reliability and error handling

Expected failure cases:

-   Historical JSON missing, invalid, or malformed.
-   Required fields missing or incorrectly typed.
-   Embedding API unavailable or rate-limited.
-   Chat completion/classification API unavailable.
-   Corrupt or stale embedding cache.
-   Empty or vague issue input.
-   No relevant retrieval candidates.
-   Resolved match with no usable action steps or resolution notes.
-   Unresolved high-similarity match.
-   Malformed structured output.
-   Citation ID or excerpt not supported by retrieved evidence.

Required behavior:

-   Raise a clear initialization error if the corpus cannot be loaded;
    do not silently create an empty index.
-   Rebuild stale/corrupt cache when possible.
-   Catch expected API/network errors at the service boundary.
-   Return a structured fallback when a recommendation cannot be
    generated reliably.
-   Never turn an API failure into an invented resolution.
-   Log technical diagnostics without exposing API keys or sensitive
    content.
-   Let Streamlit display a safe temporary-unavailability message.

The system design recommends `gpt-4o-mini` for fast classification and
generation. Keep the configured model name in one place rather than
scattering it throughout the code.

------------------------------------------------------------------------

## 12. Performance

-   Embed the fixed historical corpus once and cache the result.
-   Initialize the service once per Streamlit process/session using an
    appropriate Streamlit resource cache.
-   Embed only the incoming query at query time.
-   Retrieve a small candidate set and return the top three.
-   Keep corpus record order and vector-index mapping consistent.
-   Avoid repeated API calls when the corpus is unchanged.
-   Use concise prompts and structured outputs.

------------------------------------------------------------------------

## 13. Dependencies and configuration

  Dependency        Purpose
  ----------------- ---------------------------------------------------
  `openai`          Embeddings, classification, resolution generation
  `pydantic`        Structured result validation
  `numpy`           Vector normalization/similarity calculations
  `faiss-cpu`       Dense vector index, if using FAISS
  `rank-bm25`       BM25 keyword retrieval
  `python-dotenv`   Local environment configuration

Streamlit and SQLite are used by the application layer.

Local `.env` example:

``` env
OPENAI_API_KEY=your_api_key_here
```

Rules:

-   Never hardcode the API key.
-   Never commit `.env`.
-   Never print the key in logs or audit traces.
-   If the team creates `.env.example`, use placeholders only.
-   Confirm `rank-bm25` is included in `requirements.txt`.

------------------------------------------------------------------------

## 14. Test plan and acceptance criteria

The system design explicitly requires three demo cases.

### Test 1 --- VPN Error 504

**Input:** Cisco AnyConnect VPN connection failure with Error 504.

Expected:

-   Classify as `Network & Connectivity` with an appropriate VPN
    subcategory.
-   Retrieve the relevant VPN historical incident among the top results.
-   Show ticket ID, title, status, score, and workaround.
-   If a resolved precedent passes guardrails, return a short playbook
    with citations to actual incident text.
-   Suggest deflection only when the top hybrid score is at least
    `0.75`.

### Test 2 --- Okta SSO Loop

**Input:** Repeated redirects or login loop during Okta SSO.

Expected:

-   Classify as `Identity & Access` with an appropriate SSO subcategory.
-   Retrieve relevant Okta SSO cases.
-   If a sufficiently similar resolved incident has usable resolution
    evidence, generate a grounded playbook.
-   Every step cites a real source incident and exact supporting
    excerpt.
-   If no suitable evidence exists, return fallback rather than
    inventing steps.

### Test 3 --- Coffee spill on laptop

**Input:** Coffee spilled on a laptop.

Expected:

-   Recognize physical damage/safety sensitivity.
-   Trigger the guardrail even if a similar historical record is
    retrieved.
-   Return `is_low_confidence = True`.
-   Return an empty `playbook_steps` list.
-   Provide fallback and, when appropriate, `Tier 2 Hardware Support`.
-   Do not invent repair instructions.

### Additional tests

-   Missing/malformed JSON fields.
-   Cache hit and invalidation after corpus changes.
-   Empty affected service.
-   Empty/vague issue description.
-   No relevant candidates.
-   Resolved match without resolution content.
-   Unresolved high-similarity match.
-   BM25 normalization and hybrid ranking.
-   OpenAI API failure.
-   Invalid structured output.
-   Citation references an ID not in retrieved candidates.
-   Citation excerpt is absent from the cited record.
-   High classification confidence with low retrieval confidence, and
    vice versa.

### Acceptance checklist

-   [ ] Load and validate the canonical JSON corpus.
-   [ ] Preserve original incident metadata.
-   [ ] Cache and correctly reuse dense embeddings.
-   [ ] Build BM25 from the specified searchable fields.
-   [ ] Apply hybrid weights `0.5 / 0.3 / 0.2`.
-   [ ] Return top three similar incidents by default.
-   [ ] Use `0.75` for deflection.
-   [ ] Use `0.70` for resolution guardrails.
-   [ ] Use suitable resolved incidents as resolution evidence.
-   [ ] Generate approximately 2--4 grounded steps when evidence passes.
-   [ ] Validate every source citation.
-   [ ] Return no playbook steps on fallback.
-   [ ] Include useful retrieval and generation metadata in audit trace.
-   [ ] Pass all three required demo cases.
-   [ ] Allow Streamlit to call the service directly without FastAPI.

------------------------------------------------------------------------

## 15. Implementation sequence

Implement and test incrementally:

1.  Inspect the actual JSON file and confirm its path and schema.
2.  Create the Pydantic result models.
3.  Implement corpus loading, validation, and searchable-text
    preparation.
4.  Implement embedding generation and cache validation.
5.  Implement BM25 indexing.
6.  Implement dense retrieval and hybrid scoring.
7.  Implement `find_similar_and_deflect`; verify top-three results.
8.  Implement `classify_ticket` with structured output.
9.  Implement evidence filtering and fallback guardrails.
10. Implement grounded playbook generation and citation validation.
11. Implement audit trace generation.
12. Run the three required test cases and failure tests.
13. Integrate `RAGService` with the Streamlit application.

Do not generate the entire application in one step. Complete and test
each RAG responsibility incrementally while keeping the public method
signatures stable for the teammate integrating the UI.

------------------------------------------------------------------------

## 16. Design decisions Codex must preserve

1.  Keep the RAG subsystem isolated in `rag_service.py`.
2.  Do not introduce FastAPI or a separate API server.
3.  Use `hackathon/data/historical_incidents_200.json` as the specified
    corpus.
4.  Use dense retrieval + BM25 + exact service match.
5.  Preserve hybrid weights `0.5 / 0.3 / 0.2`.
6.  Return top three similar incidents by default.
7.  Keep the `0.75` deflection threshold separate from the `0.70`
    resolution threshold.
8.  Use only relevant resolved incidents with usable resolution evidence
    to support a playbook.
9.  Require every generated step to cite a real source ticket and
    excerpt.
10. Return no troubleshooting steps when evidence is weak, unsafe,
    contradictory, or unavailable.
11. Do not execute fixes or modify enterprise systems.
12. Do not create or submit tickets from this module.
13. Return audit metadata explaining classification, retrieval,
    guardrail decisions, generation, and citations.

------------------------------------------------------------------------

**End of RAG Design Specification**

## 17. Conversation memory and follow-up handling

The assistant must support multi-turn troubleshooting conversations. A user may ask a follow-up such as "How do I do that?" or "What if that doesn't work?" These questions depend on earlier messages and must not be treated as standalone queries.

### 17.1 Separate conversation history from historical incidents

These are two different data sources with different purposes:

- **Conversation history** stores messages exchanged in the current user chat. It provides context for follow-up questions.
- **Historical incidents** are the curated enterprise records in `hackathon/data/historical_incidents_200.json`. They are the evidence corpus used by BM25 and dense-vector retrieval.

Do not mix chat messages into the historical incident corpus or automatically treat an assistant response as a verified incident resolution. Only the curated historical incidents (or a separately approved knowledge source added by the team) may support evidence-backed resolution recommendations.

### 17.2 Persistence responsibilities

Use both Streamlit session state and SQLite, with distinct responsibilities:

| Component | Responsibility |
|---|---|
| Streamlit `st.session_state` | Maintain the active conversation in the current UI session and render messages without losing them on ordinary Streamlit reruns |
| SQLite `conversations` table | Persist conversation/session metadata across page refreshes and later retrieval |
| SQLite `messages` table | Persist each user and assistant message in order |
| Conversation context handler | Load a bounded, relevant slice of conversation history and prepare context for a follow-up |
| RAG service | Retrieve evidence from the historical incident corpus and generate grounded troubleshooting answers |

Session state is not a durable database. SQLite is the persistent store. If the app supports returning to an earlier conversation, it must have a stable conversation identifier available to retrieve it.

### 17.3 Suggested SQLite tables

Coordinate these additions with the teammate responsible for `database.py`. Do not overwrite or redesign the existing `tickets` table. Add the following tables alongside it, subject to the team's final schema agreement.

**`conversations`**

| Column | Suggested type | Purpose |
|---|---|---|
| `conversation_id` | `TEXT PRIMARY KEY` | Stable unique ID for one chat conversation |
| `created_at` | `TEXT` | ISO-8601 creation timestamp |
| `updated_at` | `TEXT` | ISO-8601 last-activity timestamp |
| `status` | `TEXT` | Optional lifecycle status, e.g. `active` or `ended` |

**`messages`**

| Column | Suggested type | Purpose |
|---|---|---|
| `message_id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Unique message row ID |
| `conversation_id` | `TEXT` | Foreign key referencing `conversations.conversation_id` |
| `role` | `TEXT` | `user` or `assistant` (optionally `system` if the implementation needs it) |
| `content` | `TEXT` | Message text |
| `created_at` | `TEXT` | ISO-8601 message timestamp |
| `metadata_json` | `TEXT` | Optional JSON for references such as retrieved incident IDs; do not store secrets |

Create an index on `messages(conversation_id, message_id)` or the equivalent timestamp/order fields so a conversation's messages can be loaded in order. Enable SQLite foreign-key enforcement on connections if foreign keys are used.

The schema above is a proposal for team agreement, not a claim that these tables already exist. The teammate implementing the database should integrate them with the existing database initialization and naming conventions.

### 17.4 Follow-up processing flow

When a new message arrives:

1. Identify the active `conversation_id`.
2. Save the incoming user message to SQLite and append it to Streamlit session state.
3. Load a bounded window of recent messages for that conversation from SQLite (or use the current session state if it is already synchronized).
4. Determine whether the new message is a follow-up to the current troubleshooting issue.
5. Resolve references such as "it", "that", "the error", or "the second step" using the conversation context.
6. If needed, rewrite the follow-up into a standalone retrieval query that preserves the original issue and the user's new question.
7. Decide whether the answer can safely use already retrieved evidence or whether fresh retrieval from the historical incident corpus is required.
8. Generate a contextual answer using the conversation context and the applicable historical evidence. Do not treat conversation history itself as proof that a technical step is correct.
9. Save the assistant response to SQLite and append it to session state.
10. Keep the same `conversation_id` for subsequent messages in the same chat.

### 17.5 When to run retrieval again

Not every follow-up needs a full new retrieval operation.

- **Clarification of an already cited step:** The assistant may explain the step using the existing retrieved evidence and conversation context, provided the explanation does not add unsupported technical instructions.
- **A new technical question or a request for another fix:** Perform fresh retrieval, or retrieve additional evidence, before giving new troubleshooting instructions.
- **Ambiguous follow-up:** Use recent conversation context to clarify what the user means. If the referent remains unclear, ask one short clarifying question rather than guessing.
- **Question unrelated to the current issue:** Handle it as a new topic and do not force the previous ticket context into the answer.
- **No supporting historical evidence:** Use the established low-confidence fallback. Do not invent steps simply because the user asks a follow-up.

For example, after the user reports a Cisco AnyConnect Error 504 and the assistant presents a DNS-related step, the follow-up "How do I do that?" can be resolved to a standalone question about the DNS step in the context of the VPN issue. If the required procedure is not supported by the retrieved incident's action steps or resolution notes, the assistant must not fabricate it.

### 17.6 Context-window and privacy rules

- Load only the recent messages needed to understand the current follow-up; do not send an unlimited conversation history to the LLM.
- Keep the original issue summary and relevant source ticket IDs available when useful.
- Avoid storing API keys, passwords, access tokens, or unnecessary personal/sensitive information in message content or metadata.
- Do not log secrets or include them in the audit trace.
- Do not use one user's conversation history as context for another user's conversation.
- The current system design omits authentication. Therefore, conversation persistence should be treated as a demo/session feature, not as secure multi-user isolation. Do not claim production-grade privacy or access control without adding and testing authentication and authorization.
- Define a simple retention/cleanup policy if persistent conversations remain in the demo database.

### 17.7 Boundary between conversation handling and `RAGService`

The public `RAGService` contract in Section 10 remains focused on classification, historical-ticket retrieval, and resolution recommendation. Conversation persistence belongs to the application/database layer, not inside the RAG service.

The application may pass the current issue and relevant conversation context to an additional answer-generation helper or extend the service contract deliberately if the team agrees. Do not silently change the three public method signatures in Section 10. Any contract change must be coordinated with the teammate integrating `app.py`.

---

## 18. Integration updates for the main application and database

The main application should coordinate the chat lifecycle with the RAG service as follows:

1. On a new chat, create a `conversation_id` and insert a row in `conversations`.
2. On each user message, persist the message with role `user` and its conversation ID.
3. Load relevant prior messages to resolve follow-ups.
4. Call the RAG service when classification, historical retrieval, or evidence-backed resolution is needed.
5. Display the returned similar incidents, citations, playbook, or fallback in Streamlit.
6. Persist the assistant response with role `assistant`; optionally save retrieved incident IDs and other non-sensitive references in `metadata_json`.
7. Update the conversation's `updated_at` value.

Do not confuse the conversation `messages` table with the existing application `tickets` table. The latter stores ticket/application records and fields such as `audit_data`; the former stores the chat transcript. Conversation messages do not automatically become tickets.

### Suggested database helper responsibilities

The teammate implementing `database.py` may add helpers along these lines, using the project's final naming conventions:

- `create_conversation(...)`
- `get_conversation(conversation_id)`
- `add_message(conversation_id, role, content, metadata=None)`
- `get_messages(conversation_id, limit=...)`
- `update_conversation_timestamp(conversation_id)`

These are suggested responsibilities, not a requirement to use these exact function names. Keep database operations in `database.py`; do not put SQLite connection logic inside `rag_service.py`.

### Updated end-to-end interaction

```text
User sends message
       |
       v
Streamlit session state
       |
       +------> Persist user message in SQLite
       |
       v
Load recent conversation messages
       |
       v
Understand / resolve follow-up context
       |
       v
Classify issue if needed
       |
       v
Hybrid retrieval over historical incident corpus
       |
       v
Evidence and safety guardrails
       |
       +-----------------------------+
       |                             |
       v                             v
Grounded contextual answer      Safe fallback
       |                             |
       +--------------+--------------+
                      |
                      v
          Persist assistant message
                 in SQLite
                      |
                      v
             Render chat response
```

---

## 19. Additional acceptance criteria for multi-turn chat

- [ ] A new chat receives a unique `conversation_id`.
- [ ] User and assistant messages are stored in SQLite and associated with that ID.
- [ ] Messages are loaded in the correct chronological order.
- [ ] Streamlit session state keeps the active chat visible across normal reruns.
- [ ] A follow-up such as "How do I do that?" is interpreted using the relevant prior context.
- [ ] A follow-up can reuse already retrieved evidence when appropriate.
- [ ] A new technical request triggers fresh evidence retrieval when needed.
- [ ] Unsupported follow-up instructions are not invented.
- [ ] Conversation messages are never automatically indexed as verified historical incidents.
- [ ] Conversation history from different conversation IDs is never mixed.
- [ ] The existing `tickets` table and RAG service public method contract remain intact unless the team explicitly agrees to change them.

---

**End of updated RAG Design Specification**
