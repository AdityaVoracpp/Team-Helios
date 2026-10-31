"""Offline unit tests. Tiny records here are test fixtures only, never runtime data."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from hackathon.rag_service import (
    ClassificationResult,
    RAGService,
    RAGServiceError,
    _GeneratedPlaybook,
)


def fixture_incidents():
    """Return isolated structural fixtures, not historical/evidence claims."""
    return [
        {
            "id": "TEST-1",
            "title": "VPN connection error",
            "description": "VPN connection returns gateway error",
            "symptoms": ["gateway error"],
            "affected_service": "Cisco AnyConnect",
            "status": "Resolved",
            "action_steps": ["Refresh the VPN client connection", "Restart the VPN client"],
            "resolution_notes": "The test fixture records a client restart.",
            "extra_schema_field": {"preserve": True},
        },
        {
            "id": "TEST-2",
            "title": "Application sign-in issue",
            "description": "Sign-in page does not load",
            "symptoms": [],
            "affected_service": "Portal",
            "status": "Open",
            "action_steps": [],
            "resolution_notes": "",
        },
    ]


class FakeBM25:
    def __init__(self, tokenized_corpus):
        self.corpus = tokenized_corpus

    def get_scores(self, query_tokens):
        return np.asarray([5.0, 0.0], dtype=np.float64)


class FakeFAISSIndex:
    def search(self, _query_vector, _count):
        return np.asarray([[0.8, 0.2]], dtype=np.float32), np.asarray([[0, 1]], dtype=np.int64)


class FakeEmbeddings:
    def __init__(self):
        self.calls = 0

    def embed_documents(self, _texts):
        self.calls += 1
        return [[3.0, 0.0], [0.0, 4.0]]


class FakeStructuredModel:
    def __init__(self, result):
        self.result = result

    def invoke(self, _messages):
        return self.result


class FakeChatClient:
    def __init__(self, result):
        self.result = result

    def with_structured_output(self, _schema, method):
        if method != "json_schema":
            raise AssertionError("expected structured JSON schema output")
        return FakeStructuredModel(self.result)


class RAGServiceTests(unittest.TestCase):
    def write_dataset(self, directory: str, records=None) -> Path:
        path = Path(directory) / "historical_incidents.json"
        path.write_text(json.dumps(fixture_incidents() if records is None else records), encoding="utf-8")
        return path

    def test_dataset_loading_preserves_all_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_dataset(directory)
            # Call the loader directly so this test needs neither API keys nor network access.
            service = object.__new__(RAGService)
            service.data_path = path
            records = service._load_incidents()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["extra_schema_field"], {"preserve": True})

    def test_missing_dataset_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with self.assertRaisesRegex(RAGServiceError, "no sample data was created"):
                RAGService(str(missing))

    def test_malformed_dataset_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_dataset(directory, [{"id": "TEST-1", "title": 4, "description": "bad"}])
            service = object.__new__(RAGService)
            service.data_path = path
            with self.assertRaisesRegex(RAGServiceError, "Invalid incident"):
                service._load_incidents()

    def test_bm25_index_uses_specified_searchable_fields_and_tokens(self):
        service = object.__new__(RAGService)
        service.incidents = fixture_incidents() + [{
            "id": "TEST-3", "title": "Payroll portal display", "description": "Unrelated display issue",
        }]
        service.search_texts = [service._prepare_incident_text(item) for item in service.incidents]
        index = service._build_bm25_index()
        tokens = service._tokenize(service.search_texts[0])
        self.assertEqual(tokens[0:2], ["vpn", "connection"])
        self.assertIn("cisco", tokens)
        scores = index.get_scores(service._tokenize("VPN gateway error"))
        self.assertGreater(scores[0], max(scores[1:]))

    def test_hybrid_score_weights_normalization_and_order(self):
        service = object.__new__(RAGService)
        service.incidents = fixture_incidents()
        service._faiss_index = FakeFAISSIndex()
        service._bm25 = FakeBM25([])
        service._vectors = np.zeros((2, 2), dtype=np.float32)
        service._embed_query = lambda _query: np.asarray([[1.0, 0.0]], dtype=np.float32)
        ranked = service._hybrid_search("VPN gateway error", "cisco anyconnect", top_k=3)
        self.assertEqual([item["record"]["id"] for item in ranked], ["TEST-1", "TEST-2"])
        self.assertAlmostEqual(ranked[0]["vector_score"], 0.9, places=6)
        self.assertEqual(ranked[0]["bm25_score"], 1.0)
        self.assertEqual(ranked[0]["exact_service_match"], 1)
        self.assertAlmostEqual(ranked[0]["hybrid_score"], 0.95, places=6)
        self.assertAlmostEqual(ranked[1]["hybrid_score"], 0.3, places=6)

    def test_embedding_cache_is_normalized_and_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            service = object.__new__(RAGService)
            service.incidents = fixture_incidents()
            service.search_texts = [service._prepare_incident_text(item) for item in service.incidents]
            service.cache_path = Path(directory) / "embeddings_cache.pkl"
            service.embedding_model_name = "text-embedding-3-small"
            service._embedding_client = FakeEmbeddings()
            vectors = service._load_or_build_embeddings()
            self.assertTrue(np.allclose(np.linalg.norm(vectors, axis=1), [1.0, 1.0]))
            self.assertEqual(service._embedding_client.calls, 1)

            second_service = object.__new__(RAGService)
            second_service.incidents = service.incidents
            second_service.search_texts = service.search_texts
            second_service.cache_path = service.cache_path
            second_service.embedding_model_name = service.embedding_model_name
            second_service._embedding_client = FakeEmbeddings()
            cached = second_service._load_or_build_embeddings()
            self.assertTrue(np.allclose(cached, vectors))
            self.assertEqual(second_service._embedding_client.calls, 0)

    def test_faiss_index_returns_nearest_normalized_vector(self):
        vectors = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        index = RAGService._build_faiss_index(vectors)
        scores, positions = index.search(np.asarray([[1.0, 0.0]], dtype=np.float32), 2)
        self.assertEqual(int(positions[0][0]), 0)
        self.assertAlmostEqual(float(scores[0][0]), 1.0, places=6)

    def test_classification_model_rejects_invalid_taxonomy_and_confidence(self):
        good = ClassificationResult(
            category="Network & Connectivity",
            subcategory="VPN",
            priority="P2",
            urgency="High",
            confidence_score=0.8,
            reasoning="Test validation only.",
        )
        self.assertEqual(good.priority, "P2")
        with self.assertRaises(ValidationError):
            ClassificationResult(
                category="Other", subcategory="x", priority="P5", urgency="x",
                confidence_score=1.2, reasoning="invalid",
            )

    def test_classification_uses_mocked_structured_llm_result(self):
        service = object.__new__(RAGService)
        service._get_chat_client = lambda: FakeChatClient({
            "category": "Network & Connectivity",
            "subcategory": "VPN",
            "priority": "P2",
            "urgency": "High",
            "confidence_score": 0.88,
            "reasoning": "The test model selected the approved taxonomy.",
        })
        result = service.classify_ticket("VPN error", "Cannot connect")
        self.assertEqual(result.category, "Network & Connectivity")
        self.assertEqual(result.confidence_score, 0.88)

    def test_generation_uses_mocked_llm_and_verbatim_source_actions(self):
        service = object.__new__(RAGService)
        service._get_chat_client = lambda: FakeChatClient({
            "confidence_score": 0.9,
            "steps": [
                {"source_ticket_id": "TEST-1", "action": "Refresh the VPN client connection"},
                {"source_ticket_id": "TEST-1", "action": "Restart the VPN client"},
            ],
        })
        candidate = {"record": fixture_incidents()[0], "hybrid_score": 0.87}
        generated = service._generate_playbook("VPN issue", [candidate])
        steps = service._validate_generated_steps(generated, [candidate])
        self.assertEqual([step.action for step in steps], [
            "Refresh the VPN client connection", "Restart the VPN client",
        ])

    def test_citation_validation_accepts_only_exact_retrieved_actions(self):
        evidence = [{
            "record": fixture_incidents()[0],
            "hybrid_score": 0.91,
        }]
        generated = _GeneratedPlaybook(
            confidence_score=0.9,
            steps=[
                {"source_ticket_id": "TEST-1", "action": "Refresh the VPN client connection"},
                {"source_ticket_id": "NOT-RETRIEVED", "action": "Restart the VPN client"},
                {"source_ticket_id": "TEST-1", "action": "Restart the VPN service"},
            ],
        )
        validated = RAGService._validate_generated_steps(generated, evidence)
        self.assertEqual(len(validated), 1)
        self.assertEqual(validated[0].source_citation.ticket_id, "TEST-1")
        self.assertEqual(validated[0].source_citation.similarity_score, 0.91)
        self.assertEqual(validated[0].source_citation.excerpt, "Refresh the VPN client connection")

    def test_low_similarity_uses_fallback_without_generation(self):
        service = object.__new__(RAGService)
        service.embedding_model_name = "text-embedding-3-small"
        service.chat_model_name = "gpt-4o-mini"
        service._hybrid_search = lambda *_args, **_kwargs: [{
            "record": fixture_incidents()[0], "hybrid_score": 0.69,
            "vector_score": 0.8, "bm25_score": 0.5, "exact_service_match": 1,
        }]
        service._generate_playbook = lambda *_args: self.fail("generation must not run below threshold")
        result = service.recommend_resolution({"title": "Issue", "description": "Details"})
        self.assertTrue(result.is_low_confidence)
        self.assertLess(result.confidence_score, 0.70)
        self.assertEqual(result.playbook_steps, [])

    def test_resolution_threshold_is_inclusive_and_returns_cited_steps(self):
        service = object.__new__(RAGService)
        service.embedding_model_name = "text-embedding-3-small"
        service.chat_model_name = "gpt-4o-mini"
        candidate = {
            "record": fixture_incidents()[0], "hybrid_score": 0.70,
            "vector_score": 0.8, "bm25_score": 0.5, "exact_service_match": 1,
        }
        service._hybrid_search = lambda *_args, **_kwargs: [candidate]
        service._generate_playbook = lambda *_args: _GeneratedPlaybook(
            confidence_score=0.9,
            steps=[
                {"source_ticket_id": "TEST-1", "action": "Refresh the VPN client connection"},
                {"source_ticket_id": "TEST-1", "action": "Restart the VPN client"},
            ],
        )
        result = service.recommend_resolution({"title": "VPN issue", "description": "Connection issue"})
        self.assertFalse(result.is_low_confidence)
        self.assertEqual(result.confidence_score, 0.70)
        self.assertEqual(len(result.playbook_steps), 2)
        self.assertEqual(result.playbook_steps[1].source_citation.ticket_id, "TEST-1")

    def test_physical_damage_uses_hardware_escalation_fallback(self):
        service = object.__new__(RAGService)
        service.embedding_model_name = "text-embedding-3-small"
        service.chat_model_name = "gpt-4o-mini"
        service._hybrid_search = lambda *_args, **_kwargs: [{
            "record": fixture_incidents()[0], "hybrid_score": 0.95,
            "vector_score": 0.9, "bm25_score": 1.0, "exact_service_match": 1,
        }]
        service._generate_playbook = lambda *_args: self.fail("physical damage must never generate steps")
        result = service.recommend_resolution({"title": "Coffee spilled on laptop", "description": "Liquid spill on keyboard"})
        self.assertTrue(result.is_low_confidence)
        self.assertEqual(result.escalation_group, "Tier 2 Hardware Support")
        self.assertEqual(result.playbook_steps, [])


if __name__ == "__main__":
    unittest.main()
