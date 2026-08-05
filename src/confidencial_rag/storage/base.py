from __future__ import annotations

import copy
import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID

from confidencial_rag.embeddings.base import EmbeddingProvider
from confidencial_rag.ingestion.base import RAGError
from confidencial_rag.ingestion.zip_validator import SafeArchiveValidator
from confidencial_rag.models import (
    KB_FORMAT,
    KB_FORMAT_VERSION,
    ChunkRecord,
    DocumentRecord,
    KnowledgeBase,
)
from confidencial_rag.vector_store.base import LocalVectorStore

REQUIRED_PACKAGE_FILES = {
    "manifest.json",
    "documents.json",
    "chunks.jsonl",
    "configuration.json",
    "README.txt",
    "vectors/index.json",
    "vectors/metadata.json",
}
PROHIBITED_PACKAGE_WORDS = ("key", "password", "credential", "secret", "token_vault", "vault", "log", "cache")


def save_package(kb: KnowledgeBase, store: LocalVectorStore, path: Path, config: dict[str, Any] | None = None) -> Path:
    package_path = Path(path).with_suffix(".zip")
    tmp = Path(tempfile.mkdtemp(prefix="kbpkg-"))
    try:
        kb.embedding_dimension = store.dimension()
        (tmp / "vectors").mkdir()
        (tmp / "manifest.json").write_text(json.dumps(kb.manifest(), indent=2), encoding="utf-8")
        documents = [document.to_dict() for document in kb.documents.values()]
        (tmp / "documents.json").write_text(json.dumps(documents, indent=2), encoding="utf-8")
        chunk_lines = [json.dumps(chunk.to_dict()) for chunk in kb.chunks.values()]
        (tmp / "chunks.jsonl").write_text("\n".join(chunk_lines) + ("\n" if chunk_lines else ""), encoding="utf-8")
        safe_config = {key: value for key, value in (config or {}).items() if "key" not in key.lower() and "secret" not in key.lower()}
        (tmp / "configuration.json").write_text(json.dumps(safe_config, indent=2), encoding="utf-8")
        (tmp / "README.txt").write_text("Confidencial RAG Version 1 package. Not encrypted.\n", encoding="utf-8")
        store.save(tmp / "vectors")
        with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(path for path in tmp.rglob("*") if path.is_file()):
                zf.write(file_path, file_path.relative_to(tmp).as_posix())
        return package_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def load_package(path: Path, embedding_provider: EmbeddingProvider | None = None) -> tuple[KnowledgeBase, LocalVectorStore]:
    validator = SafeArchiveValidator()
    staging = validator.extract_validated(Path(path), allowed_files=REQUIRED_PACKAGE_FILES)
    try:
        _reject_prohibited_names(REQUIRED_PACKAGE_FILES)
        manifest = _read_manifest(staging / "manifest.json")
        documents = _read_documents(staging / "documents.json")
        chunks = _read_chunks(staging / "chunks.jsonl", set(documents))
        store = LocalVectorStore.load(staging / "vectors")
        _validate_package_consistency(manifest, documents, chunks, store, embedding_provider)
        kb = KnowledgeBase(
            name=str(manifest["name"]),
            knowledge_base_id=str(manifest["knowledge_base_id"]),
            created_at=str(manifest["created_at"]),
            updated_at=str(manifest["updated_at"]),
            documents=documents,
            chunks=chunks,
            embedding_provider=str(manifest["embedding_provider"]),
            embedding_model=str(manifest["embedding_model"]),
            embedding_dimension=int(manifest["embedding_dimension"]),
        )
        return kb, store
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def clone_kb(kb: KnowledgeBase) -> KnowledgeBase:
    return copy.deepcopy(kb)


def replacement_chunk(chunk: ChunkRecord, text: str) -> ChunkRecord:
    return replace(chunk, text=text)


def _reject_prohibited_names(names: set[str]) -> None:
    for name in names:
        lowered = name.lower()
        if any(word in lowered for word in PROHIBITED_PACKAGE_WORDS):
            raise RAGError("Knowledge-base archive contains prohibited files.")


def _read_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RAGError("Knowledge-base manifest is malformed.") from exc
    if manifest.get("format") != KB_FORMAT or manifest.get("format_version") != KB_FORMAT_VERSION:
        raise RAGError("Unsupported knowledge-base package.")
    try:
        UUID(str(manifest.get("knowledge_base_id")))
    except ValueError as exc:
        raise RAGError("Knowledge-base package has an invalid identifier.") from exc
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", str(manifest.get("name", ""))):
        raise RAGError("Knowledge-base package has an invalid name.")
    return manifest


def _read_documents(path: Path) -> dict[str, DocumentRecord]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RAGError("Knowledge-base documents registry is malformed.") from exc
    documents: dict[str, DocumentRecord] = {}
    for row in rows:
        document = DocumentRecord(**row)
        if document.document_id in documents:
            raise RAGError("Knowledge-base archive contains duplicate document IDs.")
        documents[document.document_id] = document
    return documents


def _read_chunks(path: Path, document_ids: set[str]) -> dict[str, ChunkRecord]:
    chunks: dict[str, ChunkRecord] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        try:
            chunk = ChunkRecord(**json.loads(line))
        except json.JSONDecodeError as exc:
            raise RAGError("Knowledge-base chunk registry is malformed.") from exc
        if chunk.chunk_id in chunks:
            raise RAGError("Knowledge-base archive contains duplicate chunk IDs.")
        if chunk.document_id not in document_ids:
            raise RAGError("Knowledge-base archive contains chunks for missing documents.")
        chunks[chunk.chunk_id] = chunk
    return chunks


def _validate_package_consistency(
    manifest: dict[str, Any],
    documents: dict[str, DocumentRecord],
    chunks: dict[str, ChunkRecord],
    store: LocalVectorStore,
    embedding_provider: EmbeddingProvider | None,
) -> None:
    if int(manifest.get("document_count", -1)) != len(documents):
        raise RAGError("Manifest document count does not match package contents.")
    if int(manifest.get("chunk_count", -1)) != len(chunks):
        raise RAGError("Manifest chunk count does not match package contents.")
    if int(manifest.get("vector_count", -1)) != len(store.chunk_ids):
        raise RAGError("Manifest vector count does not match package contents.")
    if set(store.chunk_ids) != set(chunks):
        raise RAGError("Vector metadata does not match chunk registry.")
    if store.dimension() != int(manifest.get("embedding_dimension", -1)) and store.chunk_ids:
        raise RAGError("Manifest embedding dimension does not match vectors.")
    if embedding_provider is not None:
        if manifest.get("embedding_provider") != embedding_provider.provider_name:
            raise RAGError("Knowledge-base embedding provider is incompatible with this runtime.")
        if manifest.get("embedding_model") != embedding_provider.model_name:
            raise RAGError("Knowledge-base embedding model is incompatible with this runtime.")


__all__ = ["clone_kb", "load_package", "replacement_chunk", "save_package"]
