from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class DetectedEntity:
    category: str
    value: str
    start: int
    end: int


class EntityDetector(Protocol):
    """Replaceable, local entity detector contract."""

    def detect(self, text: str) -> list[DetectedEntity]: ...


class StructuredEntityDetector:
    """Deterministic detector for structured sensitive values."""

    PATTERNS = {
        "EMAIL": r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        "PHONE": r"(?<!\w)(?:\+?\d{1,3}[-. ]?)?(?:\(\d{2,4}\)|\d{2,4})[-. ]\d{3,4}[-. ]\d{4}(?!\w)",
        "IP": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "API_KEY": r"\b(?:sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{24,})\b",
        "UUID": r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b",
        "URL_SECRET": r"https?://\S*(?:token|key|secret|password)=\S+",
    }

    def detect(self, text: str) -> list[DetectedEntity]:
        entities = []
        for category, pattern in self.PATTERNS.items():
            for match in re.finditer(pattern, text):
                if category != "IP" or all(int(part) <= 255 for part in match.group().split(".")):
                    entities.append(DetectedEntity(category, match.group(), match.start(), match.end()))
        return entities


class SpacyEntityDetector:
    """Local semantic NER backed by spaCy's lightweight English pipeline."""

    DEFAULT_PUBLIC_NAMES = frozenset({
        "aws", "amazon web services", "azure", "snowflake", "microsoft azure",
        "python", "linux", "openai", "google cloud", "docker", "kubernetes",
    })
    LABEL_MAP = {"PERSON": "PERSON", "ORG": "COMPANY"}

    def __init__(self, model_name: str = "en_core_web_sm", *, nlp: Any | None = None,
                 public_names: Iterable[str] | None = None) -> None:
        self.model_name = model_name
        self._nlp = nlp
        names = self.DEFAULT_PUBLIC_NAMES if public_names is None else public_names
        self.public_names = frozenset(self._normalize(name) for name in names)

    def detect(self, text: str) -> list[DetectedEntity]:
        nlp = self._nlp or self._load_model()
        try:
            document = nlp(text)
        except Exception as exc:
            raise RuntimeError("Local NER detection failed.") from exc
        entities = []
        for entity in document.ents:
            category = self.LABEL_MAP.get(entity.label_)
            if category and self._normalize(entity.text) not in self.public_names:
                entities.append(DetectedEntity(category, entity.text, entity.start_char, entity.end_char))
        return entities

    def _load_model(self) -> Any:
        try:
            import spacy

            self._nlp = spacy.load(self.model_name)
            return self._nlp
        except Exception as exc:
            raise RuntimeError(
                f"Local NER model '{self.model_name}' could not be loaded; external request blocked."
            ) from exc

    @staticmethod
    def _normalize(value: str) -> str:
        return " ".join(value.casefold().split())


class CompositeEntityDetector:
    """Runs independent detectors locally and combines their entity spans."""

    def __init__(self, detectors: Iterable[EntityDetector]) -> None:
        self.detectors = tuple(detectors)

    def detect(self, text: str) -> list[DetectedEntity]:
        entities = [entity for detector in self.detectors for entity in detector.detect(text)]
        return sorted(entities, key=lambda entity: (entity.start, -(entity.end - entity.start)))


def default_entity_detector() -> CompositeEntityDetector:
    return CompositeEntityDetector([StructuredEntityDetector(), SpacyEntityDetector()])


__all__ = [
    "CompositeEntityDetector", "DetectedEntity", "EntityDetector", "SpacyEntityDetector",
    "StructuredEntityDetector", "default_entity_detector",
]
