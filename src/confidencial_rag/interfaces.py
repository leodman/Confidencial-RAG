"""Stable interfaces for replaceable Confidencial RAG modules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    text: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchResult:
    chunk: DocumentChunk
    score: float


@dataclass(frozen=True)
class SanitizedRequest:
    query: str
    context: Sequence[DocumentChunk]
    vault_reference: str


class VectorStore(ABC):
    @abstractmethod
    def add(self, chunks: Iterable[DocumentChunk]) -> None:
        """Add or update chunks."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> Sequence[SearchResult]:
        """Return the most relevant chunks."""

    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Remove all chunks belonging to one document."""

    @abstractmethod
    def save(self, path: Path) -> None:
        """Persist the store."""

    @abstractmethod
    def load(self, path: Path) -> None:
        """Restore the store."""


class PrivacyGateway(ABC):
    @abstractmethod
    def sanitize(self, query: str, context: Sequence[DocumentChunk]) -> SanitizedRequest:
        """Create a reversible, safe outbound request or fail closed."""

    @abstractmethod
    def restore(self, response: str, vault_reference: str) -> str:
        """Restore protected values locally."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, request: SanitizedRequest) -> str:
        """Generate a response from sanitized input only."""
