"""Compatibility re-exports for the Version 1 modular service packages."""

from confidencial_rag.chunking.base import RecursiveChunker as RecursiveChunker
from confidencial_rag.embeddings.base import EmbeddingProvider as EmbeddingProvider
from confidencial_rag.embeddings.sentence_transformers import HashEmbeddingProvider as HashEmbeddingProvider
from confidencial_rag.embeddings.sentence_transformers import SentenceTransformersEmbeddingProvider as SentenceTransformersEmbeddingProvider
from confidencial_rag.ingestion.base import DocumentLoader as DocumentLoader
from confidencial_rag.ingestion.base import RAGError as RAGError
from confidencial_rag.ingestion.base import SUPPORTED_EXTENSIONS as SUPPORTED_EXTENSIONS
from confidencial_rag.ingestion.zip_validator import SafeArchiveValidator as SafeArchiveValidator
from confidencial_rag.ingestion.zip_validator import SafeZip as SafeZip
from confidencial_rag.llm.base import ExtractiveLLM as ExtractiveLLM
from confidencial_rag.llm.base import OpenAIProvider as OpenAIProvider
from confidencial_rag.privacy.base import PrivacyGateway as PrivacyGateway
from confidencial_rag.privacy.base import PrivacySession as PrivacySession
from confidencial_rag.retrieval.base import RetrievalResult as RetrievalResult
from confidencial_rag.retrieval.base import SemanticRetriever as SemanticRetriever
from confidencial_rag.storage.base import clone_kb as clone_kb
from confidencial_rag.storage.base import load_package as load_package
from confidencial_rag.storage.base import replacement_chunk as replacement_chunk
from confidencial_rag.storage.base import save_package as save_package
from confidencial_rag.vector_store.base import LocalVectorStore as LocalVectorStore

__all__ = [
    "DocumentLoader",
    "EmbeddingProvider",
    "ExtractiveLLM",
    "HashEmbeddingProvider",
    "LocalVectorStore",
    "OpenAIProvider",
    "PrivacyGateway",
    "PrivacySession",
    "RAGError",
    "RecursiveChunker",
    "RetrievalResult",
    "SUPPORTED_EXTENSIONS",
    "SafeArchiveValidator",
    "SafeZip",
    "SemanticRetriever",
    "SentenceTransformersEmbeddingProvider",
    "clone_kb",
    "load_package",
    "replacement_chunk",
    "save_package",
]
