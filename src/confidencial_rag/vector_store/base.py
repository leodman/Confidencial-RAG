from __future__ import annotations

import copy
import json
from pathlib import Path

from confidencial_rag.ingestion.base import RAGError
from confidencial_rag.models import KnowledgeBase


class LocalVectorStore:
    def __init__(self) -> None:
        self.vectors: list[list[float]] = []
        self.chunk_ids: list[str] = []

    def clone(self) -> "LocalVectorStore":
        cloned = LocalVectorStore()
        cloned.vectors = copy.deepcopy(self.vectors)
        cloned.chunk_ids = list(self.chunk_ids)
        return cloned

    def add(self, chunk_ids: list[str], vectors: list[list[float]]) -> None:
        for vector in vectors:
            if self.vectors and len(vector) != self.dimension():
                raise RAGError("Embedding dimension mismatch.")
        self.chunk_ids.extend(chunk_ids)
        self.vectors.extend([list(map(float, vector)) for vector in vectors])

    def remove_document(self, knowledge_base: KnowledgeBase, document_id: str) -> None:
        keep = [i for i, cid in enumerate(self.chunk_ids) if knowledge_base.chunks[cid].document_id != document_id]
        self.vectors = [self.vectors[i] for i in keep]
        self.chunk_ids = [self.chunk_ids[i] for i in keep]

    def search(self, query: list[float], top_k: int = 5, min_score: float = 0.1) -> list[tuple[str, float]]:
        scores = [(cid, float(sum(a * b for a, b in zip(vector, query)))) for cid, vector in zip(self.chunk_ids, self.vectors)]
        scores.sort(key=lambda item: item[1], reverse=True)
        return [(cid, score) for cid, score in scores[:top_k] if score >= min_score]

    def dimension(self) -> int:
        return len(self.vectors[0]) if self.vectors else 0

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "index.json").write_text(json.dumps({"vectors": self.vectors}), encoding="utf-8")
        metadata = {"chunk_ids": self.chunk_ids, "dimension": self.dimension(), "vector_count": len(self.chunk_ids)}
        (path / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "LocalVectorStore":
        store = cls()
        index = json.loads((path / "index.json").read_text(encoding="utf-8"))
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        store.vectors = index["vectors"]
        store.chunk_ids = metadata["chunk_ids"]
        if len(store.vectors) != len(store.chunk_ids):
            raise RAGError("Vector and metadata counts do not match.")
        if store.vectors and metadata.get("dimension") != len(store.vectors[0]):
            raise RAGError("Invalid vector metadata dimension.")
        return store


__all__ = ["LocalVectorStore"]
