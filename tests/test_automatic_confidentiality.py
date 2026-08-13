from dataclasses import dataclass

import pytest

from confidencial_rag.controller import ApplicationController, KnowledgeBaseError
from confidencial_rag.embeddings.sentence_transformers import HashEmbeddingProvider
from confidencial_rag.privacy import (
    CompositeEntityDetector,
    PrivacyGateway,
    SpacyEntityDetector,
    StructuredEntityDetector,
)


@dataclass
class FakeEntity:
    text: str
    label_: str
    start_char: int
    end_char: int


class FakeDocument:
    def __init__(self, entities):
        self.ents = entities


class SyntheticNLP:
    semantic = {
        "John Smith": "PERSON",
        "Claro Enterprise Solutions": "ORG",
        "Claro": "ORG",
        "Azure": "ORG",
        "Snowflake": "ORG",
        "AWS": "ORG",
        "Microsoft": "ORG",
        "Microsoft Azure": "ORG",
        "Google Cloud": "ORG",
    }

    def __call__(self, text):
        entities = []
        # Longest first prevents the synthetic Claro span duplicating the longer company.
        occupied = []
        for value, label in sorted(self.semantic.items(), key=lambda item: -len(item[0])):
            start = 0
            while (index := text.find(value, start)) >= 0:
                end = index + len(value)
                if not any(index < other_end and end > other_start for other_start, other_end in occupied):
                    entities.append(FakeEntity(value, label, index, end))
                    occupied.append((index, end))
                start = end
        return FakeDocument(entities)


def local_gateway():
    detector = CompositeEntityDetector([
        StructuredEntityDetector(),
        SpacyEntityDetector(nlp=SyntheticNLP()),
    ])
    return PrivacyGateway(detector=detector)


def test_local_ner_structured_detection_manual_override_and_restoration():
    original = (
        "John Smith from Claro Enterprise Solutions called +1 415-555-0134 about Project Aurora. "
        "Email john.smith@example.com. John Smith later contacted Claro."
    )
    gateway = local_gateway()
    sanitized, vault, report = gateway.sanitize(original, ["Project Aurora"])
    assert sanitized.count("<PERSON_0001>") == 2
    assert "<COMPANY_0001>" in sanitized and "<COMPANY_0002>" in sanitized
    assert "<EMAIL_0001>" in sanitized and "<PHONE_0001>" in sanitized
    assert "<CUSTOM_0001>" in sanitized
    assert gateway.restore(sanitized, vault) == original
    assert report["automatic"] == {
        "PERSON": 2, "COMPANY": 2, "PHONE": 1, "EMAIL": 1,
    }
    assert report["custom"] == 1
    assert report["total_replacements"] == 7


@pytest.mark.parametrize(
    "public_name",
    ["Azure", "Snowflake", "AWS", "Microsoft Azure", "Google Cloud"],
)
def test_public_product_and_technology_names_remain_visible(public_name):
    sanitized, _, report = local_gateway().sanitize(f"The platform uses {public_name} for testing.")
    assert public_name in sanitized
    assert report["total_replacements"] == 0


def test_plain_company_name_is_not_exempted_by_public_product_allowlist():
    sanitized, _, report = local_gateway().sanitize("Microsoft signed the agreement.")
    assert "Microsoft" not in sanitized
    assert report["automatic"]["COMPANY"] == 1


def test_ordinary_capitalized_pdf_style_phrases_are_not_people():
    text = "Security Architecture and Service Availability are described in the following section."
    sanitized, _, report = local_gateway().sanitize(text)
    assert sanitized == text
    assert "PERSON" not in report["automatic"]


def test_runtime_detection_does_not_use_network(monkeypatch):
    import socket

    monkeypatch.setattr(socket, "create_connection", lambda *args, **kwargs: pytest.fail("network used"))
    sanitized, _, _ = local_gateway().sanitize("John Smith emailed john@example.com")
    assert "John Smith" not in sanitized and "john@example.com" not in sanitized


class FailingNLP:
    def __call__(self, text):
        raise RuntimeError("synthetic NER failure")


class RecordingProvider:
    def __init__(self):
        self.called = False

    def generate(self, question, results, citations):
        self.called = True
        return "should not happen"


def test_ner_failure_fails_closed_before_external_provider(tmp_path, monkeypatch):
    controller = ApplicationController(runtime_dir=tmp_path, embedding_provider=HashEmbeddingProvider())
    controller.start()
    controller.create_knowledge_base("fail_closed")
    document = tmp_path / "public.txt"
    document.write_text("Synthetic evidence for the question.", encoding="utf-8")
    controller.ingest_files([document])
    provider = RecordingProvider()
    detector = CompositeEntityDetector([StructuredEntityDetector(), SpacyEntityDetector(nlp=FailingNLP())])
    monkeypatch.setattr(
        "confidencial_rag.controller.PrivacyGateway", lambda: PrivacyGateway(detector=detector)
    )

    with pytest.raises(KnowledgeBaseError, match="Confidentiality detection failed"):
        controller.ask(
            "What is the evidence?", mode="External, confidential", minimum_similarity=0.0,
            external_provider=provider,
        )
    assert provider.called is False


def test_missing_ner_model_has_clear_error(monkeypatch):
    detector = SpacyEntityDetector()
    monkeypatch.setattr(detector, "_load_model", lambda: (_ for _ in ()).throw(
        RuntimeError("Local NER model could not be loaded; external request blocked.")
    ))
    with pytest.raises(RuntimeError, match="external request blocked"):
        detector.detect("John Smith")
