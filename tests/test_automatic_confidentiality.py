import pytest

from confidencial_rag.controller import ApplicationController, KnowledgeBaseError
from confidencial_rag.embeddings.sentence_transformers import HashEmbeddingProvider
from confidencial_rag.ingestion.base import RAGError
from confidencial_rag.privacy import ConfidentialityPolicy, PrivacyGateway


EXAMPLE = (
    "John Smith from Claro Enterprise Solutions is working on Project Aurora using Azure and "
    "Snowflake. Contact john.smith@example.com or +1 415-555-0134. John Smith leads the work."
)


def test_automatic_entities_manual_override_report_and_restoration():
    gateway = PrivacyGateway()
    sanitized, vault, report = gateway.sanitize(EXAMPLE, ["Project Aurora"])

    assert "<PERSON_0001>" in sanitized
    assert "<COMPANY_0001>" in sanitized
    assert "<EMAIL_0001>" in sanitized
    assert "<PHONE_0001>" in sanitized
    assert "<CUSTOM_0001>" in sanitized
    assert "Azure" in sanitized and "Snowflake" in sanitized
    assert sanitized.count("<PERSON_0001>") == 2
    assert gateway.restore(sanitized, vault) == EXAMPLE
    assert report["automatic"] == {"PERSON": 2, "COMPANY": 1, "EMAIL": 1, "PHONE": 1}
    assert report["custom"] == 1
    assert report["total_replacements"] == 6


def test_policy_is_configurable():
    policy = ConfidentialityPolicy()
    policy.rules["PERSON"] = False
    sanitized, _, report = PrivacyGateway(policy=policy).sanitize("John Smith emailed jane@example.com")
    assert "John Smith" in sanitized
    assert "jane@example.com" not in sanitized
    assert "PERSON" not in report["automatic"]


def test_detector_is_local_and_does_not_use_network(monkeypatch):
    import socket

    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: pytest.fail("network used"))
    sanitized, _, _ = PrivacyGateway().sanitize("Jane Doe at jane@example.com")
    assert "Jane Doe" not in sanitized


class BrokenDetector:
    def detect(self, text):
        raise RuntimeError("synthetic detector failure")


class RecordingProvider:
    def __init__(self):
        self.called = False

    def generate(self, question, results, citations):
        self.called = True
        return "should not happen"


def test_confidential_controller_fails_closed_when_detection_fails(tmp_path, monkeypatch):
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider())
    controller.start()
    controller.create_knowledge_base("fail_closed")
    document = tmp_path / "public.txt"
    document.write_text("Synthetic evidence for the question.", encoding="utf-8")
    controller.ingest_files([document])
    provider = RecordingProvider()

    monkeypatch.setattr(
        "confidencial_rag.controller.PrivacyGateway",
        lambda: PrivacyGateway(detector=BrokenDetector()),
    )
    with pytest.raises(KnowledgeBaseError, match="Confidentiality detection failed"):
        controller.ask(
            "What is the evidence?",
            mode="External, confidential",
            minimum_similarity=0.0,
            external_provider=provider,
        )
    assert provider.called is False


def test_token_mapping_failure_is_safe():
    session = PrivacyGateway().create_session()
    session._token = lambda *args: (_ for _ in ()).throw(RAGError("mapping failed"))
    with pytest.raises(RAGError):
        session.sanitize("jane@example.com")
