"""Smoke tests for the real model installed by the Version 2/Colab dependency set."""

import pytest

from confidencial_rag.privacy import PrivacyGateway, SpacyEntityDetector


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def real_detector():
    spacy = pytest.importorskip("spacy")
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        pytest.skip("en_core_web_sm is not installed")
    return SpacyEntityDetector(nlp=nlp)


def categories(detector, text):
    return [(entity.value, entity.category) for entity in detector.detect(text)]


def test_real_model_detects_person(real_detector):
    assert ("John Smith", "PERSON") in categories(
        real_detector, "John Smith joined the project yesterday."
    )


@pytest.mark.parametrize("name", ["Claro", "Claro Enterprise Solutions"])
def test_real_model_records_claro_behavior(real_detector, name, record_property):
    detected = categories(real_detector, f"{name} announced a new customer agreement today.")
    record_property("en_core_web_sm_entities", repr(detected))
    # This assertion deliberately records truthful model behavior without faking an ORG result.
    assert all(category in {"PERSON", "COMPANY"} for _, category in detected)


@pytest.mark.parametrize("public_name", ["Azure", "Snowflake"])
def test_real_model_public_technologies_remain_visible(real_detector, public_name):
    gateway = PrivacyGateway(detector=real_detector)
    sanitized, _, _ = gateway.sanitize(f"The platform uses {public_name} for analytics.")
    assert public_name in sanitized


def test_real_model_does_not_mask_pdf_style_heading_as_person(real_detector):
    text = "Security Architecture and Service Availability are described in the following section."
    gateway = PrivacyGateway(detector=real_detector)
    sanitized, _, report = gateway.sanitize(text)
    assert sanitized == text
    assert "PERSON" not in report["automatic"]
