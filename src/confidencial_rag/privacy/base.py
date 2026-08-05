from __future__ import annotations

import re
from collections import Counter

from confidencial_rag.ingestion.base import RAGError


class PrivacySession:
    def __init__(self, custom_terms: list[str] | None = None) -> None:
        self.custom_terms = sorted([term for term in (custom_terms or []) if term.strip()], key=len, reverse=True)
        self.vault: dict[str, str] = {}
        self._reverse: dict[tuple[str, str], str] = {}
        self._counts: Counter[str] = Counter()
        self._category_next: Counter[str] = Counter()

    @property
    def counts(self) -> dict[str, int]:
        return dict(self._counts)

    def sanitize(self, text: str) -> str:
        sanitized = text
        for term in self.custom_terms:
            sanitized = re.sub(re.escape(term), lambda match: self._token("CUSTOM", match.group(0)), sanitized)
        for category, pattern in PrivacyGateway.PATTERNS.items():
            sanitized = re.sub(pattern, lambda match, cat=category: self._token(cat, match.group(0)), sanitized)
        return sanitized

    def restore(self, text: str) -> str:
        restored = text
        for token, value in sorted(self.vault.items(), key=lambda item: len(item[0]), reverse=True):
            restored = restored.replace(token, value)
        return restored

    def _token(self, category: str, value: str) -> str:
        key = (category, value)
        if key not in self._reverse:
            self._category_next[category] += 1
            token = f"<{category}_{self._category_next[category]:04d}>"
            while token in self.vault:
                self._category_next[category] += 1
                token = f"<{category}_{self._category_next[category]:04d}>"
            self._reverse[key] = token
            self.vault[token] = value
        self._counts[category] += 1
        return self._reverse[key]


class PrivacyGateway:
    PATTERNS = {
        "EMAIL": r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
        "PHONE": r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b",
        "IP": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
        "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
        "API_KEY": r"\b(?:sk-[A-Za-z0-9_-]{12,}|[A-Za-z0-9_-]{24,})\b",
        "UUID": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "URL_SECRET": r"https?://\S*(?:token|key|secret|password)=\S+",
    }

    def create_session(self, custom_terms: list[str] | None = None) -> PrivacySession:
        return PrivacySession(custom_terms)

    def sanitize(self, text: str, custom_terms: list[str] | None = None) -> tuple[str, dict[str, str], dict[str, int]]:
        session = self.create_session(custom_terms)
        sanitized = session.sanitize(text)
        return sanitized, dict(session.vault), session.counts

    def restore(self, text: str, vault: dict[str, str]) -> str:
        for token, value in sorted(vault.items(), key=lambda item: len(item[0]), reverse=True):
            text = text.replace(token, value)
        return text

    def validate_no_leakage(self, payload: str, session: PrivacySession) -> None:
        leaked = [value for value in session.vault.values() if value and value in payload]
        if leaked:
            raise RAGError("Privacy validation failed; external request was blocked.")


__all__ = ["PrivacyGateway", "PrivacySession"]
