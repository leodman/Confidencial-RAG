from __future__ import annotations

import re
from collections import Counter

from confidencial_rag.ingestion.base import RAGError

from .detection import DetectedEntity, DeterministicEntityDetector, EntityDetector
from .policy import ConfidentialityPolicy


class PrivacySession:
    def __init__(self, custom_terms: list[str] | None = None, *, detector: EntityDetector | None = None,
                 policy: ConfidentialityPolicy | None = None) -> None:
        self.custom_terms = sorted({term.strip() for term in (custom_terms or []) if term.strip()}, key=len, reverse=True)
        self.detector = detector or DeterministicEntityDetector()
        self.policy = policy or ConfidentialityPolicy()
        self.vault: dict[str, str] = {}
        self._reverse: dict[tuple[str, str], str] = {}
        self._automatic: Counter[str] = Counter()
        self._custom = 0
        self._category_next: Counter[str] = Counter()

    @property
    def counts(self) -> dict[str, object]:
        automatic = dict(self._automatic)
        report: dict[str, object] = {
            "automatic": automatic,
            "custom": self._custom,
            "total_replacements": sum(automatic.values()) + self._custom,
        }
        # Preserve Version 1 consumers while exposing the clearer Version 2 audit structure.
        report.update(automatic)
        report["CUSTOM"] = self._custom
        return report

    def sanitize(self, text: str) -> str:
        candidates: list[tuple[int, int, str, str, bool]] = []
        for term in self.custom_terms:
            candidates.extend((m.start(), m.end(), "CUSTOM", m.group(), True)
                              for m in re.finditer(re.escape(term), text))
        try:
            detected = self.detector.detect(text)
        except Exception as exc:
            raise RAGError("Confidentiality detection failed; external request was blocked.") from exc
        for entity in detected:
            if self.policy.is_confidential(entity.category):
                candidates.append((entity.start, entity.end, entity.category, entity.value, False))

        # Manual spans are authoritative; otherwise prefer the longest detection at a position.
        candidates.sort(key=lambda item: (not item[4], item[0], -(item[1] - item[0])))
        selected: list[tuple[int, int, str, str, bool]] = []
        for candidate in candidates:
            if not any(candidate[0] < item[1] and candidate[1] > item[0] for item in selected):
                selected.append(candidate)
        sanitized = text
        for start, end, category, value, manual in sorted(selected, reverse=True):
            sanitized = sanitized[:start] + self._token(category, value, manual) + sanitized[end:]
        return sanitized

    def restore(self, text: str) -> str:
        for token, value in sorted(self.vault.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(token, value)
        return text

    def _token(self, category: str, value: str, manual: bool) -> str:
        key = (category, value)
        if key not in self._reverse:
            self._category_next[category] += 1
            token = f"<{category}_{self._category_next[category]:04d}>"
            self._reverse[key] = token
            self.vault[token] = value
        if manual:
            self._custom += 1
        else:
            self._automatic[category] += 1
        return self._reverse[key]


class PrivacyGateway:
    PATTERNS = DeterministicEntityDetector.STRUCTURED_PATTERNS

    def __init__(self, detector: EntityDetector | None = None, policy: ConfidentialityPolicy | None = None) -> None:
        self.detector = detector or DeterministicEntityDetector()
        self.policy = policy or ConfidentialityPolicy()

    def create_session(self, custom_terms: list[str] | None = None) -> PrivacySession:
        return PrivacySession(custom_terms, detector=self.detector, policy=self.policy)

    def sanitize(self, text: str, custom_terms: list[str] | None = None) -> tuple[str, dict[str, str], dict[str, object]]:
        session = self.create_session(custom_terms)
        sanitized = session.sanitize(text)
        return sanitized, dict(session.vault), session.counts

    def restore(self, text: str, vault: dict[str, str]) -> str:
        return PrivacySession().restore(text) if not vault else self._restore(text, vault)

    @staticmethod
    def _restore(text: str, vault: dict[str, str]) -> str:
        for token, value in sorted(vault.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(token, value)
        return text

    def validate_no_leakage(self, payload: str, session: PrivacySession) -> None:
        if any(value and value in payload for value in session.vault.values()):
            raise RAGError("Privacy validation failed; external request was blocked.")


__all__ = ["PrivacyGateway", "PrivacySession", "DetectedEntity"]
