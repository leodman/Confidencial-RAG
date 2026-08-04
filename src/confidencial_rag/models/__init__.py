from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import uuid

KB_FORMAT = "confidencial-rag-knowledge-base"
KB_FORMAT_VERSION = 1
DEFAULT_EMBEDDING_PROVIDER = "sentence_transformers"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_id(prefix: str, *parts: str) -> str:
    joined = "|".join(parts)
    return f"{prefix}_{hashlib.sha256(joined.encode('utf-8')).hexdigest()[:16]}"


@dataclass
class TextUnit:
    text: str
    page_number: int | None = None
    section: str | None = None
    character_start: int | None = None
    character_end: int | None = None


@dataclass
class DocumentRecord:
    document_id: str
    original_filename: str
    relative_path: str
    file_type: str
    content_hash: str
    file_size: int
    ingested_at: str
    status: str = "indexed"
    page_count: int | None = None
    chunk_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    text: str
    chunk_index: int
    page_number: int | None = None
    section: str | None = None
    source_path: str = ""
    character_start: int | None = None
    character_end: int | None = None
    content_hash: str = ""

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class KnowledgeBase:
    name: str
    knowledge_base_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utcnow)
    updated_at: str = field(default_factory=utcnow)
    documents: dict[str, DocumentRecord] = field(default_factory=dict)
    chunks: dict[str, ChunkRecord] = field(default_factory=dict)
    embedding_provider: str = DEFAULT_EMBEDDING_PROVIDER
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    embedding_dimension: int = 0

    def manifest(self) -> dict[str, object]:
        self.updated_at = utcnow()
        return {
            "format": KB_FORMAT,
            "format_version": KB_FORMAT_VERSION,
            "knowledge_base_id": self.knowledge_base_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "document_count": len(self.documents),
            "chunk_count": len(self.chunks),
            "vector_count": len(self.chunks),
            "embedding_provider": self.embedding_provider,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
        }
