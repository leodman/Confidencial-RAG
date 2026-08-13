from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DetectedEntity:
    category: str
    value: str
    start: int
    end: int


class EntityDetector(Protocol):
    """Replaceable, local entity detector contract."""

    def detect(self, text: str) -> list[DetectedEntity]: ...


class DeterministicEntityDetector:
    """Conservative, offline detector for obvious structured and named entities.

    Named-entity rules intentionally favor precision over recall. This is an
    experimental baseline that can later be supplemented by a local NLP model.
    """

    STRUCTURED_PATTERNS = {
        "EMAIL": r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        "PHONE": r"(?<!\w)(?:\+?\d{1,3}[-. ]?)?(?:\(\d{2,4}\)|\d{2,4})[-. ]\d{3,4}[-. ]\d{4}(?!\w)",
        "IP": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "API_KEY": r"\b(?:sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{24,})\b",
        "UUID": r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b",
        "URL_SECRET": r"https?://\S*(?:token|key|secret|password)=\S+",
    }
    PUBLIC_NAMES = {
        "AWS", "Amazon Web Services", "Azure", "Snowflake", "Microsoft", "Python",
        "Linux", "OpenAI", "Google Cloud", "Java", "Docker", "Kubernetes",
    }
    COMPANY_SUFFIXES = (
        "Inc", "Incorporated", "Corp", "Corporation", "Company", "Co", "LLC", "Ltd",
        "Limited", "Group", "Holdings", "Solutions", "Systems", "Technologies", "Enterprises",
    )
    _name_word = r"[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)?"

    def detect(self, text: str) -> list[DetectedEntity]:
        entities: list[DetectedEntity] = []
        for category, pattern in self.STRUCTURED_PATTERNS.items():
            for match in re.finditer(pattern, text):
                if category != "IP" or all(int(part) <= 255 for part in match.group().split(".")):
                    entities.append(self._entity(category, match))

        suffixes = "|".join(map(re.escape, self.COMPANY_SUFFIXES))
        company_pattern = rf"\b(?:{self._name_word}\s+){{1,4}}(?:{suffixes})\b"
        for match in re.finditer(company_pattern, text):
            if match.group() not in self.PUBLIC_NAMES:
                entities.append(self._entity("COMPANY", match))

        occupied = [(entity.start, entity.end) for entity in entities]
        person_pattern = rf"\b{self._name_word}\s+{self._name_word}(?:\s+{self._name_word})?\b"
        excluded_first = {"Project", "Product", "Microsoft", "Amazon", "Google", "Internal"}
        for match in re.finditer(person_pattern, text):
            value = match.group()
            overlaps = any(match.start() < end and match.end() > start for start, end in occupied)
            if not overlaps and value not in self.PUBLIC_NAMES and value.split()[0] not in excluded_first:
                entities.append(self._entity("PERSON", match))
        return sorted(entities, key=lambda entity: (entity.start, -(entity.end - entity.start)))

    @staticmethod
    def _entity(category: str, match: re.Match[str]) -> DetectedEntity:
        return DetectedEntity(category, match.group(), match.start(), match.end())


__all__ = ["DetectedEntity", "DeterministicEntityDetector", "EntityDetector"]
