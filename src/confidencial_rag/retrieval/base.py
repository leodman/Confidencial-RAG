from __future__ import annotations

from dataclasses import dataclass

from confidencial_rag.models import ChunkRecord, KnowledgeBase
from confidencial_rag.vector_store.base import LocalVectorStore


@dataclass(frozen=True)
class RetrievalResult:
    chunk: ChunkRecord
    score: float


class SemanticRetriever:
    def __init__(self, vector_store: LocalVectorStore) -> None:
        self.vector_store = vector_store

    def search(self, knowledge_base: KnowledgeBase, query_vector: list[float], top_k: int, minimum_similarity: float) -> list[RetrievalResult]:
        return [
            RetrievalResult(knowledge_base.chunks[chunk_id], score)
            for chunk_id, score in self.vector_store.search(query_vector, top_k, minimum_similarity)
        ]


__all__ = ["RetrievalResult", "SemanticRetriever"]
