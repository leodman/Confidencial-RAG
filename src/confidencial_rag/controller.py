from __future__ import annotations

import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any

from .models import DocumentRecord, KnowledgeBase, sha256_bytes, stable_id, utcnow
from .rag_services import (
    DocumentLoader,
    ExtractiveLLM,
    LocalVectorStore,
    OpenAIProvider,
    PrivacyGateway,
    RAGError,
    RecursiveChunker,
    SafeZip,
    SentenceTransformersEmbeddingProvider,
    clone_kb,
    load_package,
    replacement_chunk,
    save_package,
)
from .state import SystemState


class InvalidStateTransition(RuntimeError):
    pass


class KnowledgeBaseError(RuntimeError):
    pass


@dataclass
class ApplicationController:
    state: SystemState = SystemState.OFF
    runtime_dir: Path | None = None
    embedding_provider: Any | None = None
    active_knowledge_base: str | None = None
    kb: KnowledgeBase | None = None
    vector_store: LocalVectorStore = field(default_factory=LocalVectorStore)
    last_operation: str = "Idle"
    warnings: list[str] = field(default_factory=list)
    exported_path: Path | None = None
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _api_key: str | None = field(default=None, init=False, repr=False)
    _provider_with_key: Any | None = field(default=None, init=False, repr=False)
    _staging_dirs: list[Path] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.runtime_dir = Path(self.runtime_dir or tempfile.mkdtemp(prefix="confidencial-rag-"))
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if self.embedding_provider is None:
            self.embedding_provider = SentenceTransformersEmbeddingProvider()

    def start(self) -> SystemState:
        with self._lock:
            self._require(SystemState.OFF)
            self.state = SystemState.STARTING
            self.state = SystemState.EMPTY
            self.last_operation = "System started"
            return self.state

    def create_knowledge_base(self, name: str) -> dict[str, object]:
        with self._lock:
            self._require_any(SystemState.EMPTY, SystemState.READY)
            clean = self._validate_name(name)
            self.kb = KnowledgeBase(
                clean,
                embedding_provider=self.embedding_provider.provider_name,
                embedding_model=self.embedding_provider.model_name,
                embedding_dimension=int(getattr(self.embedding_provider, "dimension", 0)),
            )
            self.vector_store = LocalVectorStore()
            self.active_knowledge_base = clean
            self.state = SystemState.READY
            self.last_operation = "Knowledge base created"
            return self.kb.manifest()

    def load_knowledge_base(self, name: str) -> dict[str, object]:
        with self._lock:
            self._require_any(SystemState.EMPTY, SystemState.READY)
            clean = self._validate_name(name)
            candidate = self.runtime_dir / f"{clean}.zip"
            if not candidate.exists():
                raise KnowledgeBaseError("Knowledge base was not found in this runtime.")
            return self.import_knowledge_base(candidate)

    def ingest_files(self, files: list[Any] | None, chunk_size: int = 1000, chunk_overlap: int = 150) -> list[dict[str, object]]:
        with self._lock:
            self._require(SystemState.READY)
            if self.kb is None:
                raise KnowledgeBaseError("Create a knowledge base before indexing documents.")
            previous_kb = clone_kb(self.kb)
            previous_store = self.vector_store.clone()
            self.state = SystemState.INGESTING
            try:
                paths = self._prepare_upload_paths(files or [])
                staged_kb = clone_kb(self.kb)
                staged_store = self.vector_store.clone()
                report = self._stage_documents(paths, staged_kb, staged_store, chunk_size, chunk_overlap)
                self.kb = staged_kb
                self.vector_store = staged_store
                self.kb.embedding_dimension = self.vector_store.dimension()
                self.state = SystemState.READY
                self.last_operation = f"Indexed {len(report)} file(s)"
                return report
            except Exception as exc:
                self.kb = previous_kb
                self.vector_store = previous_store
                self.state = SystemState.READY
                raise KnowledgeBaseError(self._safe_error(exc)) from None
            finally:
                self._cleanup_staging_dirs()

    def ask(
        self,
        question: str,
        mode: str = "Local only",
        top_k: int = 5,
        minimum_similarity: float = 0.1,
        custom_terms: str = "",
        api_key: str = "",
        model: str = "gpt-4o-mini",
        confirm_non_confidential: bool = False,
        external_provider: Any | None = None,
    ) -> dict[str, object]:
        with self._lock:
            self._require(SystemState.READY)
            if self.kb is None or not self.kb.chunks or not self.vector_store.chunk_ids:
                raise KnowledgeBaseError("Chat requires an indexed knowledge base.")
            if not question.strip():
                raise KnowledgeBaseError("Enter a question before sending.")
            self.state = SystemState.CHATTING
            try:
                qv = self.embedding_provider.embed([question])[0]
                hits = self.vector_store.search(qv, int(top_k), float(minimum_similarity))
                results = [(self.kb.chunks[cid], score) for cid, score in hits]
                citations = self._citations(results)
                if not results:
                    answer = "I could not find sufficient evidence in the indexed documents."
                    response = self._response(answer, citations, {}, "", False)
                elif mode == "Local only":
                    answer = ExtractiveLLM().generate(question, results, citations)
                    response = self._response(answer, citations, {}, "", False)
                elif mode == "External, confidential":
                    response = self._ask_external_confidential(question, results, citations, custom_terms, api_key, model, external_provider)
                else:
                    if not confirm_non_confidential:
                        raise KnowledgeBaseError("Non-confidential external test mode requires explicit confirmation.")
                    provider = external_provider or OpenAIProvider(api_key, model)
                    answer = provider.generate(question, results, citations)
                    response = self._response(answer, citations, {}, "", True)
                self.state = SystemState.READY
                self.last_operation = "Answered question"
                return response
            except KnowledgeBaseError:
                self.state = SystemState.READY
                raise
            except Exception as exc:
                self.state = SystemState.READY
                raise KnowledgeBaseError(self._safe_error(exc)) from None

    def save_knowledge_base(self) -> Path:
        with self._lock:
            self._require_active_ready()
            return self.export_knowledge_base(self.runtime_dir / f"{self.kb.name}.zip")

    def export_knowledge_base(self, path: Path | None = None) -> Path:
        with self._lock:
            self._require_active_ready()
            self.state = SystemState.EXPORTING
            try:
                destination = path or (self.runtime_dir / f"{self.kb.name}.zip")
                self.exported_path = save_package(self.kb, self.vector_store, destination, {"secrets_persisted": False})
                self.state = SystemState.READY
                self.last_operation = "Knowledge base exported"
                return self.exported_path
            except Exception as exc:
                self.state = SystemState.READY
                raise KnowledgeBaseError(self._safe_error(exc)) from None

    def import_knowledge_base(self, path: Path) -> dict[str, object]:
        with self._lock:
            self._require_any(SystemState.EMPTY, SystemState.READY)
            previous = (self.kb, self.vector_store, self.active_knowledge_base)
            self.state = SystemState.IMPORTING
            try:
                imported_kb, imported_store = load_package(Path(path), self.embedding_provider)
                self.kb = imported_kb
                self.vector_store = imported_store
                self.active_knowledge_base = imported_kb.name
                self.state = SystemState.READY
                self.last_operation = "Knowledge base imported"
                return imported_kb.manifest()
            except Exception as exc:
                self.kb, self.vector_store, self.active_knowledge_base = previous
                self.state = SystemState.READY if previous[0] else SystemState.EMPTY
                raise KnowledgeBaseError(self._safe_error(exc)) from None

    def remove_document(self, document_id: str) -> bool:
        with self._lock:
            self._require_active_ready()
            if document_id not in self.kb.documents:
                raise KnowledgeBaseError("Document was not found.")
            self.vector_store.remove_document(self.kb, document_id)
            for chunk_id, chunk in list(self.kb.chunks.items()):
                if chunk.document_id == document_id:
                    del self.kb.chunks[chunk_id]
            del self.kb.documents[document_id]
            self.kb.embedding_dimension = self.vector_store.dimension()
            self.last_operation = "Document removed"
            return True

    def status(self) -> dict[str, object]:
        manifest = self.kb.manifest() if self.kb else {}
        return {
            "state": self.state.value,
            "active_knowledge_base": self.active_knowledge_base,
            "runtime_mode": "Local only",
            "embedding_provider": getattr(self.embedding_provider, "provider_name", "unknown"),
            "embedding_model": getattr(self.embedding_provider, "model_name", "unknown"),
            "embedding_dimension": getattr(self.embedding_provider, "dimension", 0),
            "document_count": len(self.kb.documents) if self.kb else 0,
            "chunk_count": len(self.kb.chunks) if self.kb else 0,
            "vector_count": len(self.vector_store.chunk_ids),
            "last_operation": self.last_operation,
            "warnings": self.warnings,
            "exported_path": str(self.exported_path) if self.exported_path else None,
            **{f"kb_{key}": value for key, value in manifest.items()},
        }

    def shutdown(self) -> SystemState:
        with self._lock:
            self.state = SystemState.SHUTTING_DOWN
            self._api_key = None
            self._provider_with_key = None
            self._cleanup_staging_dirs()
            self.active_knowledge_base = None
            self.kb = None
            self.vector_store = LocalVectorStore()
            self.warnings.clear()
            self.state = SystemState.OFF
            self.last_operation = "Safe shutdown"
            return self.state

    def _prepare_upload_paths(self, files: list[Any]) -> list[Path]:
        if len(files) > 200:
            raise KnowledgeBaseError("Too many files were uploaded.")
        total = 0
        paths: list[Path] = []
        for item in files:
            path = Path(item if isinstance(item, (str, Path)) else getattr(item, "name", item))
            size = path.stat().st_size
            total += size
            if size > 52428800 or total > 524288000:
                raise KnowledgeBaseError("Uploaded files exceed configured size limits.")
            if path.suffix.lower() == ".zip":
                expanded, staging = SafeZip().expand(path)
                self._staging_dirs.append(staging)
                paths.extend(expanded)
            elif path.suffix.lower() in DocumentLoader.__module__ and False:
                paths.append(path)
            else:
                paths.append(path)
        return paths

    def _stage_documents(
        self,
        paths: list[Path],
        staged_kb: KnowledgeBase,
        staged_store: LocalVectorStore,
        chunk_size: int,
        chunk_overlap: int,
    ) -> list[dict[str, object]]:
        loader = DocumentLoader()
        chunker = RecursiveChunker(chunk_size, chunk_overlap)
        report: list[dict[str, object]] = []
        for path in paths:
            data = path.read_bytes()
            content_hash = sha256_bytes(data)
            if any(document.content_hash == content_hash for document in staged_kb.documents.values()):
                report.append({"file": path.name, "status": "duplicate", "warning": "Already indexed"})
                continue
            units, metadata, warnings = loader.load_units(path)
            document_id = stable_id("doc", content_hash, path.name)
            document = DocumentRecord(
                document_id=document_id,
                original_filename=path.name,
                relative_path=path.name,
                file_type=path.suffix.lower(),
                content_hash=content_hash,
                file_size=len(data),
                ingested_at=utcnow(),
                status="indexed",
                page_count=metadata.get("page_count"),
                warnings=warnings,
            )
            chunks = chunker.chunks(document, units)
            document.chunk_count = len(chunks)
            vectors = self.embedding_provider.embed([chunk.text for chunk in chunks]) if chunks else []
            staged_kb.documents[document_id] = document
            for chunk in chunks:
                staged_kb.chunks[chunk.chunk_id] = chunk
            staged_store.add([chunk.chunk_id for chunk in chunks], vectors)
            report.append({"file": path.name, "status": document.status, "chunks": document.chunk_count, "warnings": "; ".join(warnings)})
        return report

    def _ask_external_confidential(
        self,
        question: str,
        results: list[tuple[Any, float]],
        citations: list[dict[str, Any]],
        custom_terms: str,
        api_key: str,
        model: str,
        external_provider: Any | None,
    ) -> dict[str, object]:
        gateway = PrivacyGateway()
        session = gateway.create_session(custom_terms.splitlines())
        sanitized_question = session.sanitize(question)
        sanitized_citations = []
        for citation in citations:
            sanitized_citations.append({**citation, "filename": session.sanitize(str(citation["filename"])), "excerpt": session.sanitize(str(citation["excerpt"]))})
        sanitized_results = []
        for chunk, score in results:
            sanitized_results.append((replacement_chunk(chunk, session.sanitize(chunk.text)), score))
        preview = "Question:\n" + sanitized_question + "\n\nContext:\n" + "\n---\n".join(chunk.text for chunk, _score in sanitized_results)
        gateway.validate_no_leakage(preview, session)
        provider = external_provider or OpenAIProvider(api_key, model)
        answer = provider.generate(sanitized_question, sanitized_results, sanitized_citations)
        outbound = sanitized_question + preview + jsonish(sanitized_citations)
        gateway.validate_no_leakage(outbound, session)
        return self._response(session.restore(answer), citations, session.counts, preview, True)

    def _citations(self, results: list[tuple[Any, float]]) -> list[dict[str, Any]]:
        assert self.kb is not None
        citations = []
        for number, (chunk, score) in enumerate(results, 1):
            document = self.kb.documents[chunk.document_id]
            location = f"page {chunk.page_number}" if chunk.page_number else (chunk.section or "")
            citations.append(
                {
                    "number": number,
                    "filename": document.original_filename,
                    "page_or_section": location,
                    "score": score,
                    "chunk_id": chunk.chunk_id,
                    "excerpt": chunk.text[:500],
                }
            )
        return citations

    def _response(self, answer: str, citations: list[dict[str, Any]], privacy: dict[str, int], preview: str, external_called: bool) -> dict[str, object]:
        return {
            "answer": answer,
            "citations": citations,
            "evidence": citations,
            "privacy_report": privacy,
            "sanitized_preview": preview,
            "external_called": external_called,
        }

    def _require_active_ready(self) -> None:
        self._require(SystemState.READY)
        if self.kb is None:
            raise KnowledgeBaseError("An active knowledge base is required.")

    def _require(self, state: SystemState) -> None:
        if self.state is not state:
            raise InvalidStateTransition(f"Operation requires state {state.value}.")

    def _require_any(self, *states: SystemState) -> None:
        if self.state not in states:
            allowed = ", ".join(state.value for state in states)
            raise InvalidStateTransition(f"Operation requires one of: {allowed}.")

    def _validate_name(self, name: str) -> str:
        clean = name.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", clean):
            raise KnowledgeBaseError("Use 1-64 letters, numbers, hyphens, or underscores; start with a letter or number.")
        return clean

    def _safe_error(self, exc: Exception) -> str:
        if isinstance(exc, (KnowledgeBaseError, RAGError)):
            return str(exc)
        return "The operation failed safely. Please verify the inputs and try again."

    def _cleanup_staging_dirs(self) -> None:
        for directory in self._staging_dirs:
            shutil.rmtree(directory, ignore_errors=True)
        self._staging_dirs.clear()


def jsonish(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True)
