"""Evidence-grounded RAG service for Helios ITSM Assist.

Conversation persistence and Streamlit session state belong to the application
layer. This module only classifies issues and retrieves evidence from the
curated incident corpus.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pickle
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

try:  # Imported lazily enough for offline unit tests and actionable errors.
    import faiss  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised where the dependency is absent
    faiss = None

try:
    from rank_bm25 import BM25Okapi  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - exercised where the dependency is absent
    BM25Okapi = None

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


LOGGER = logging.getLogger(__name__)
DEFAULT_DATA_PATH = "hackathon/data/historical_incidents_200.json"
EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
TOP_K = 3
DEFLECTION_THRESHOLD = 0.75
RESOLUTION_THRESHOLD = 0.70
SCORING_WEIGHTS = {"vector": 0.50, "bm25": 0.30, "exact_service_match": 0.20}
ALLOWED_CATEGORIES = {
    "Network & Connectivity",
    "Identity & Access",
    "Hardware",
    "Cloud & Infrastructure",
    "Software & Applications",
}


class RAGServiceError(RuntimeError):
    """Controlled service error suitable for display by the Streamlit layer."""


class ClassificationResult(BaseModel):
    category: Literal[
        "Network & Connectivity",
        "Identity & Access",
        "Hardware",
        "Cloud & Infrastructure",
        "Software & Applications",
    ]
    subcategory: str
    priority: Literal["P1", "P2", "P3", "P4"]
    urgency: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str


class SimilarTicket(BaseModel):
    id: str
    title: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    status: str
    resolution_summary: str
    quick_workaround: str


class DeflectionResult(BaseModel):
    deflection_suggested: bool
    similar_tickets: List[SimilarTicket] = Field(default_factory=list)


class Citation(BaseModel):
    ticket_id: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    excerpt: str


class PlaybookStep(BaseModel):
    step_number: int
    action: str
    rationale: str
    source_citation: Citation


class ResolutionResult(BaseModel):
    is_low_confidence: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    fallback_reason: Optional[str] = None
    escalation_group: Optional[str] = None
    playbook_steps: List[PlaybookStep] = Field(default_factory=list)
    summary_notes: str
    audit_trace: Dict[str, Any] = Field(default_factory=dict)


class _GeneratedStep(BaseModel):
    """LLM may select and order source actions; it cannot author new actions."""

    source_ticket_id: str
    action: str


class _GeneratedPlaybook(BaseModel):
    confidence_score: float = Field(ge=0.0, le=1.0)
    steps: List[_GeneratedStep]


class _Incident(BaseModel):
    """Validated core fields while preserving every additional corpus field."""

    model_config = ConfigDict(extra="allow")
    id: str
    title: str
    description: str
    status: str = "Unknown"
    symptoms: List[str] = Field(default_factory=list)
    affected_service: str = ""
    action_steps: List[str] = Field(default_factory=list)
    resolution_notes: str = ""

    @field_validator("id", "title", "description", "status", "affected_service", "resolution_notes", mode="before")
    @classmethod
    def text_fields(cls, value: Any) -> Any:
        if value is None:
            return ""
        if not isinstance(value, str):
            raise ValueError("expected a string")
        return value

    @field_validator("symptoms", "action_steps", mode="before")
    @classmethod
    def list_of_strings(cls, value: Any) -> Any:
        if value is None:
            return []
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError("expected a list of strings")
        return value


class RAGService:
    """Classification, hybrid retrieval, deflection, and grounded playbooks."""

    def __init__(self, data_path: str = DEFAULT_DATA_PATH):
        if load_dotenv is not None:
            load_dotenv()
        self.data_path = Path(data_path)
        self.cache_path = self.data_path.parent / "embeddings_cache.pkl"
        self.embedding_model_name = os.getenv("OPENAI_EMBEDDING_MODEL", EMBEDDING_MODEL)
        self.chat_model_name = os.getenv("OPENAI_CHAT_MODEL") or os.getenv("LLM_MODEL", CHAT_MODEL)
        self.incidents = self._load_incidents()
        if faiss is None:
            raise RAGServiceError("FAISS is unavailable. Install dependencies from requirements.txt.")
        if BM25Okapi is None:
            raise RAGServiceError("rank-bm25 is unavailable. Install dependencies from requirements.txt.")
        self.search_texts = [self._prepare_incident_text(item) for item in self.incidents]
        self._bm25 = self._build_bm25_index()
        self._embedding_client = self._create_embedding_client()
        self._vectors = self._load_or_build_embeddings()
        self._faiss_index = self._build_faiss_index(self._vectors)
        self._chat_client = None

    def _load_incidents(self) -> List[Dict[str, Any]]:
        if not self.data_path.is_file():
            raise RAGServiceError(
                f"Historical incident dataset not found at '{self.data_path}'. "
                "Provide hackathon/data/historical_incidents_200.json; no sample data was created."
            )
        try:
            raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RAGServiceError(f"Could not read incident dataset '{self.data_path}': {exc}") from exc
        if isinstance(raw, dict):
            raw = raw.get("incidents")
        if not isinstance(raw, list) or not raw:
            raise RAGServiceError("Incident dataset must be a non-empty JSON list (or an object with an 'incidents' list).")

        incidents: List[Dict[str, Any]] = []
        seen_ids = set()
        for position, record in enumerate(raw):
            if not isinstance(record, dict):
                raise RAGServiceError(f"Incident at index {position} must be a JSON object.")
            try:
                validated = _Incident.model_validate(record)
            except Exception as exc:
                raise RAGServiceError(f"Invalid incident at index {position}: {exc}") from exc
            if not validated.id.strip() or not validated.title.strip():
                raise RAGServiceError(f"Incident at index {position} requires non-empty 'id' and 'title'.")
            if validated.id in seen_ids:
                raise RAGServiceError(f"Duplicate incident ID '{validated.id}' at index {position}.")
            seen_ids.add(validated.id)
            # Keep the original mapping intact, including fields unknown to this module.
            incidents.append(dict(record))
        return incidents

    @staticmethod
    def _prepare_incident_text(record: Dict[str, Any]) -> str:
        symptoms = record.get("symptoms") or []
        if not isinstance(symptoms, list):
            symptoms = []
        parts = [record.get("title", ""), record.get("description", ""), " ".join(str(x) for x in symptoms), record.get("affected_service", "")]
        return re.sub(r"\s+", " ", " ".join(str(part or "") for part in parts)).strip()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", text.lower())

    def _build_bm25_index(self) -> Any:
        if BM25Okapi is None:
            raise RAGServiceError("rank-bm25 is unavailable. Install dependencies from requirements.txt.")
        return BM25Okapi([self._tokenize(text) for text in self.search_texts])

    def _create_embedding_client(self) -> Any:
        if not os.getenv("OPENAI_API_KEY"):
            raise RAGServiceError("OPENAI_API_KEY is not set. Add it to .env before initializing the RAG service.")
        try:
            from langchain_openai import OpenAIEmbeddings
        except ImportError as exc:
            raise RAGServiceError("langchain-openai is unavailable. Install dependencies from requirements.txt.") from exc
        try:
            return OpenAIEmbeddings(
                model=self.embedding_model_name,
                base_url=os.getenv("OPENAI_BASE_URL") or None,
            )
        except Exception as exc:
            raise RAGServiceError(f"Could not initialize the OpenAI embeddings client: {type(exc).__name__}.") from exc

    def _corpus_fingerprint(self) -> str:
        payload = json.dumps(self.search_texts, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load_or_build_embeddings(self) -> np.ndarray:
        fingerprint = self._corpus_fingerprint()
        if self.cache_path.is_file():
            try:
                with self.cache_path.open("rb") as cache_file:
                    cache = pickle.load(cache_file)
                if (
                    cache.get("model") == self.embedding_model_name
                    and cache.get("fingerprint") == fingerprint
                    and cache.get("ids") == [item["id"] for item in self.incidents]
                ):
                    vectors = np.asarray(cache["vectors"], dtype=np.float32)
                    if vectors.ndim == 2 and vectors.shape[0] == len(self.incidents) and np.isfinite(vectors).all():
                        return self._normalize_vectors(vectors)
            except Exception as exc:  # A corrupt or stale cache is rebuilt.
                LOGGER.warning("Ignoring unreadable embedding cache (%s).", type(exc).__name__)
        try:
            vectors = np.asarray(self._embedding_client.embed_documents(self.search_texts), dtype=np.float32)
        except Exception as exc:
            raise RAGServiceError(f"Could not embed the incident corpus: {type(exc).__name__}.") from exc
        if vectors.ndim != 2 or vectors.shape[0] != len(self.incidents) or not np.isfinite(vectors).all():
            raise RAGServiceError("Embedding provider returned a malformed incident-vector matrix.")
        vectors = self._normalize_vectors(vectors)
        self._write_embedding_cache(fingerprint, vectors)
        return vectors

    def _write_embedding_cache(self, fingerprint: str, vectors: np.ndarray) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache = {
            "model": self.embedding_model_name,
            "fingerprint": fingerprint,
            "ids": [item["id"] for item in self.incidents],
            "vectors": vectors,
        }
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile("wb", dir=self.cache_path.parent, delete=False) as temporary_file:
                temporary_path = Path(temporary_file.name)
                pickle.dump(cache, temporary_file, protocol=pickle.HIGHEST_PROTOCOL)
            temporary_path.replace(self.cache_path)
        except OSError as exc:
            LOGGER.warning("Could not persist embedding cache (%s).", type(exc).__name__)
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return np.divide(vectors, norms, out=np.zeros_like(vectors), where=norms > 0)

    @staticmethod
    def _build_faiss_index(vectors: np.ndarray) -> Any:
        if faiss is None:
            raise RAGServiceError("FAISS is unavailable. Install dependencies from requirements.txt.")
        index = faiss.IndexFlatIP(int(vectors.shape[1]))
        index.add(np.ascontiguousarray(vectors, dtype=np.float32))
        return index

    def _embed_query(self, query: str) -> np.ndarray:
        try:
            vector = np.asarray(self._embedding_client.embed_query(query), dtype=np.float32).reshape(1, -1)
        except Exception as exc:
            raise RAGServiceError(f"Could not embed the incoming issue: {type(exc).__name__}.") from exc
        if not np.isfinite(vector).all() or vector.shape[1] != self._vectors.shape[1]:
            raise RAGServiceError("Embedding provider returned a malformed query vector.")
        return self._normalize_vectors(vector)

    def _hybrid_search(self, query: str, affected_service: Optional[str] = None, top_k: int = TOP_K) -> List[Dict[str, Any]]:
        if not query.strip() or top_k <= 0 or not self.incidents:
            return []
        query_vector = self._embed_query(query)
        distances, positions = self._faiss_index.search(query_vector, len(self.incidents))
        dense_raw = np.zeros(len(self.incidents), dtype=np.float32)
        for score, position in zip(distances[0], positions[0]):
            if 0 <= position < len(dense_raw):
                dense_raw[position] = float(score)
        # Normalized cosine vectors produce [-1, 1]; map onto [0, 1].
        dense_scores = np.clip((dense_raw + 1.0) / 2.0, 0.0, 1.0)
        bm25_raw = np.asarray(self._bm25.get_scores(self._tokenize(query)), dtype=np.float64)
        if bm25_raw.size != len(self.incidents):
            raise RAGServiceError("BM25 index returned a score count that does not match the corpus.")
        low, high = float(np.min(bm25_raw)), float(np.max(bm25_raw))
        if high > low:
            bm25_scores = (bm25_raw - low) / (high - low)
        else:
            bm25_scores = np.ones_like(bm25_raw) if high > 0 else np.zeros_like(bm25_raw)
        service = (affected_service or "").strip().casefold()
        ranked = []
        for position, incident in enumerate(self.incidents):
            exact_service = int(bool(service) and service == str(incident.get("affected_service", "")).strip().casefold())
            vector_score = float(dense_scores[position])
            bm25_score = float(np.clip(bm25_scores[position], 0.0, 1.0))
            hybrid_score = (
                SCORING_WEIGHTS["vector"] * vector_score
                + SCORING_WEIGHTS["bm25"] * bm25_score
                + SCORING_WEIGHTS["exact_service_match"] * exact_service
            )
            ranked.append({
                "record": incident,
                "vector_score": vector_score,
                "bm25_score": bm25_score,
                "exact_service_match": exact_service,
                "hybrid_score": float(np.clip(hybrid_score, 0.0, 1.0)),
            })
        ranked.sort(key=lambda candidate: candidate["hybrid_score"], reverse=True)
        return ranked[:top_k]

    def classify_ticket(self, title: str, description: str, affected_service: Optional[str] = None) -> ClassificationResult:
        issue = self._format_issue(title, description, affected_service)
        categories = ", ".join(f'"{category}"' for category in sorted(ALLOWED_CATEGORIES))
        try:
            model = self._get_chat_client().with_structured_output(ClassificationResult, method="json_schema")
            result = model.invoke([
                (
                    "system",
                    "Classify an enterprise IT issue using this exact schema. "
                    f"category must be exactly one of: {categories}. "
                    'priority must be exactly one of "P1", "P2", "P3", or "P4" (code only; no label). '
                    "Urgency should be a concise assessment. Do not invent facts or use dataset/UI category labels "
                    "that are not in the allowed category list. Return confidence from 0 to 1 and concise reasoning.",
                ),
                ("human", issue),
            ])
            return ClassificationResult.model_validate(result)
        except Exception as exc:
            LOGGER.warning("Ticket classification failed (%s).", type(exc).__name__)
            raise RAGServiceError(f"Ticket classification is temporarily unavailable ({type(exc).__name__}).") from exc

    def find_similar_and_deflect(
        self,
        title: str,
        description: str,
        affected_service: Optional[str] = None,
        top_k: int = 3,
    ) -> DeflectionResult:
        query = self._format_issue(title, description, affected_service)
        try:
            candidates = self._hybrid_search(query, affected_service, top_k)
        except RAGServiceError as exc:
            LOGGER.warning("Similar incident retrieval failed (%s).", type(exc).__name__)
            return DeflectionResult(deflection_suggested=False)
        similar = [self._to_similar_ticket(candidate) for candidate in candidates]
        return DeflectionResult(
            deflection_suggested=bool(candidates and candidates[0]["hybrid_score"] >= DEFLECTION_THRESHOLD),
            similar_tickets=similar,
        )

    def recommend_resolution(self, ticket_dict: Dict[str, Any], top_k: int = 3) -> ResolutionResult:
        title = str(ticket_dict.get("title") or "")
        description = str(ticket_dict.get("description") or "")
        service = ticket_dict.get("affected_service")
        query = self._format_issue(title, description, service)
        base_trace = self._base_audit_trace(ticket_dict, top_k)
        try:
            candidates = self._hybrid_search(query, service, top_k)
        except RAGServiceError as exc:
            base_trace["retrieval"]["error"] = type(exc).__name__
            return self._fallback(base_trace, "Historical evidence is temporarily unavailable; contact human IT support.", None, 0.0)
        base_trace["retrieval"]["candidates"] = [self._candidate_trace(item) for item in candidates]
        if not candidates:
            return self._fallback(base_trace, "No relevant historical incident evidence was found; contact human IT support.", None, 0.0)

        top_score = candidates[0]["hybrid_score"]
        is_physical = self._is_safety_sensitive(f"{title} {description}")
        if is_physical:
            base_trace["guardrail"].update({"safety_sensitive": True, "decision": "fallback"})
            return self._fallback(
                base_trace,
                "Physical damage or another safety-sensitive condition requires specialist inspection.",
                "Tier 2 Hardware Support",
                min(top_score, RESOLUTION_THRESHOLD - 0.01),
            )
        if top_score < RESOLUTION_THRESHOLD:
            base_trace["guardrail"]["decision"] = "fallback_low_similarity"
            return self._fallback(
                base_trace,
                "Historical precedent confidence is below 70%; contact the appropriate human IT support group.",
                self._known_escalation_group(candidates, ticket_dict),
                min(top_score, RESOLUTION_THRESHOLD - 0.01),
            )

        evidence = [item for item in candidates if self._usable_resolved_evidence(item["record"])]
        if not evidence:
            base_trace["guardrail"]["decision"] = "fallback_no_resolved_evidence"
            return self._fallback(
                base_trace,
                "No suitable resolved incident contains usable troubleshooting evidence; contact human IT support.",
                self._known_escalation_group(candidates, ticket_dict),
                min(top_score, RESOLUTION_THRESHOLD - 0.01),
            )
        try:
            generated = self._generate_playbook(query, evidence)
            steps = self._validate_generated_steps(generated, evidence)
        except Exception as exc:
            LOGGER.warning("Grounded playbook generation failed (%s).", type(exc).__name__)
            base_trace["generation"].update({"decision": "fallback", "error": type(exc).__name__})
            return self._fallback(
                base_trace,
                "A reliable evidence-backed playbook could not be generated; contact human IT support.",
                self._known_escalation_group(evidence, ticket_dict),
                min(top_score, RESOLUTION_THRESHOLD - 0.01),
            )
        final_confidence = min(top_score, generated.confidence_score)
        base_trace["generation"].update({
            "decision": "accepted" if steps and final_confidence >= RESOLUTION_THRESHOLD else "fallback",
            "source_ticket_ids": sorted({step.source_citation.ticket_id for step in steps}),
            "confidence_score": final_confidence,
        })
        base_trace["guardrail"].update({"decision": "pass" if final_confidence >= RESOLUTION_THRESHOLD else "fallback_low_generation_confidence"})
        if not steps or len(steps) < 2 or final_confidence < RESOLUTION_THRESHOLD:
            return self._fallback(
                base_trace,
                "Generated evidence did not meet the 70% confidence and citation requirements; contact human IT support.",
                self._known_escalation_group(evidence, ticket_dict),
                min(final_confidence, RESOLUTION_THRESHOLD - 0.01),
            )
        return ResolutionResult(
            is_low_confidence=False,
            confidence_score=final_confidence,
            playbook_steps=steps[:4],
            summary_notes="These steps are copied from resolved historical incidents and are suggestions, not guaranteed fixes.",
            audit_trace=base_trace,
        )

    def _get_chat_client(self) -> Any:
        if self._chat_client is None:
            if not os.getenv("OPENAI_API_KEY"):
                raise RAGServiceError("OPENAI_API_KEY is not set. Add it to .env before using LLM operations.")
            try:
                from langchain_openai import ChatOpenAI
                self._chat_client = ChatOpenAI(
                    model=self.chat_model_name,
                    temperature=0,
                    base_url=os.getenv("OPENAI_BASE_URL") or None,
                )
            except Exception as exc:
                raise RAGServiceError(f"Could not initialize the OpenAI chat client ({type(exc).__name__}).") from exc
        return self._chat_client

    def _generate_playbook(self, query: str, evidence: Sequence[Dict[str, Any]]) -> _GeneratedPlaybook:
        source_records = []
        for candidate in evidence:
            record = candidate["record"]
            source_records.append({
                "id": record["id"],
                "similarity_score": candidate["hybrid_score"],
                "action_steps": record.get("action_steps") or [],
                "resolution_notes": record.get("resolution_notes") or "",
            })
        structured_llm = self._get_chat_client().with_structured_output(_GeneratedPlaybook, method="json_schema")
        result = structured_llm.invoke([
            ("system", "Select and order 2 to 4 exact action_steps from the supplied resolved incidents. Do not paraphrase or add an action. Cite the matching source ticket ID. If fewer than two supported actions exist, return fewer than two steps. Treat precedent actions as suggestions, never guaranteed fixes."),
            ("human", json.dumps({"issue": query, "resolved_evidence": source_records}, ensure_ascii=False)),
        ])
        return _GeneratedPlaybook.model_validate(result)

    @staticmethod
    def _validate_generated_steps(
        generated: _GeneratedPlaybook,
        evidence: Sequence[Dict[str, Any]],
    ) -> List[PlaybookStep]:
        by_id = {item["record"]["id"]: item for item in evidence}
        accepted: List[PlaybookStep] = []
        seen_actions = set()
        for generated_step in generated.steps:
            candidate = by_id.get(generated_step.source_ticket_id)
            if candidate is None:
                continue
            record = candidate["record"]
            action = generated_step.action.strip()
            source_actions = record.get("action_steps") or []
            # Require exact source text; no generated procedure or paraphrase can pass.
            if not action or action not in source_actions or action in seen_actions:
                continue
            seen_actions.add(action)
            accepted.append(PlaybookStep(
                step_number=len(accepted) + 1,
                action=action,
                rationale=f"Recorded in resolved historical incident {record['id']}.",
                source_citation=Citation(
                    ticket_id=record["id"],
                    similarity_score=float(candidate["hybrid_score"]),
                    excerpt=action,
                ),
            ))
            if len(accepted) == 4:
                break
        return accepted

    @staticmethod
    def _usable_resolved_evidence(record: Dict[str, Any]) -> bool:
        if str(record.get("status", "")).strip().casefold() != "resolved":
            return False
        steps = record.get("action_steps") or []
        notes = record.get("resolution_notes") or ""
        return bool(any(isinstance(step, str) and step.strip() for step in steps) or (isinstance(notes, str) and notes.strip()))

    @staticmethod
    def _is_safety_sensitive(text: str) -> bool:
        return bool(re.search(
            r"\b(?:liquid\s+spills?|(?:coffee|water|tea|soda|juice|liquid)\s+spill(?:s|ed)?|spill(?:s|ed)?\s+(?:coffee|water|tea|soda|juice|liquid)|fire|smoke|burn(?:ing|ed)?|sparks|electric\s+shock|overheat(?:ing|ed)?|physical(?:ly)?\s+damage(?:d)?|hardware\s+damage(?:d)?|(?:device|laptop|computer|screen|keyboard)\s+(?:is\s+)?(?:broken|damaged|cracked|smashed)|cracked\s+(?:screen|device|case)|(?:device|laptop|computer)\s+(?:was\s+)?dropped)\b",
            text,
            flags=re.IGNORECASE,
        ))

    @staticmethod
    def _format_issue(title: str, description: str, affected_service: Optional[str]) -> str:
        parts = [f"Title: {title.strip()}" if title and title.strip() else "", f"Description: {description.strip()}" if description and description.strip() else ""]
        if affected_service and affected_service.strip():
            parts.append(f"Affected service: {affected_service.strip()}")
        return "\n".join(parts).strip()

    @staticmethod
    def _to_similar_ticket(candidate: Dict[str, Any]) -> SimilarTicket:
        record = candidate["record"]
        return SimilarTicket(
            id=str(record.get("id", "")),
            title=str(record.get("title", "")),
            similarity_score=float(candidate["hybrid_score"]),
            status=str(record.get("status", "Unknown")),
            resolution_summary=str(record.get("resolution_notes") or ""),
            quick_workaround=str((record.get("action_steps") or [""])[0] or ""),
        )

    @staticmethod
    def _candidate_trace(candidate: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ticket_id": candidate["record"].get("id"),
            "vector_score": candidate["vector_score"],
            "bm25_score": candidate["bm25_score"],
            "exact_service_match": candidate["exact_service_match"],
            "hybrid_score": candidate["hybrid_score"],
            "status": candidate["record"].get("status"),
        }

    @staticmethod
    def _known_escalation_group(candidates: Sequence[Dict[str, Any]], ticket_dict: Dict[str, Any]) -> Optional[str]:
        explicit = ticket_dict.get("assignment_group")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        for candidate in candidates:
            record = candidate["record"]
            group = record.get("assignment_group")
            if isinstance(group, str) and group.strip():
                return group.strip()
        return None

    def _base_audit_trace(self, ticket_dict: Dict[str, Any], top_k: int) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input": {
                "title": str(ticket_dict.get("title") or ""),
                "description": str(ticket_dict.get("description") or ""),
                "affected_service": str(ticket_dict.get("affected_service") or ""),
            },
            "classification": {
                key: ticket_dict[key]
                for key in ("category", "subcategory", "priority", "urgency", "confidence_score")
                if key in ticket_dict
            },
            "retrieval": {
                "embedding_model": self.embedding_model_name,
                "top_k": max(int(top_k), 0),
                "scoring_weights": dict(SCORING_WEIGHTS),
                "candidates": [],
            },
            "guardrail": {"threshold": RESOLUTION_THRESHOLD, "is_low_confidence": True},
            "generation": {"model": self.chat_model_name, "prompt_version": "grounded-actions-v1"},
        }

    @staticmethod
    def _fallback(
        audit_trace: Dict[str, Any],
        reason: str,
        escalation_group: Optional[str],
        confidence: float,
    ) -> ResolutionResult:
        audit_trace.setdefault("guardrail", {})["is_low_confidence"] = True
        audit_trace["guardrail"]["fallback_reason"] = reason
        return ResolutionResult(
            is_low_confidence=True,
            confidence_score=float(np.clip(confidence, 0.0, RESOLUTION_THRESHOLD - 0.01)),
            fallback_reason=reason,
            escalation_group=escalation_group,
            playbook_steps=[],
            summary_notes=reason,
            audit_trace=audit_trace,
        )
