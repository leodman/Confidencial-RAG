"""Central application lifecycle controller and synthetic milestone storage."""

from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

from .state import SystemState


class InvalidStateTransition(RuntimeError):
    """Raised when an operation is not valid in the current state."""


class KnowledgeBaseError(RuntimeError):
    """Raised for a safe, user-facing synthetic knowledge-base error."""


@dataclass
class ApplicationController:
    """Coordinate lifecycle operations without coupling the UI to modules.

    This milestone persists only synthetic JSON manifests in a temporary runtime
    directory. Concrete storage, ingestion, retrieval, privacy, and LLM services
    will be injected here as the project grows.
    """

    state: SystemState = SystemState.OFF
    active_knowledge_base: str | None = None
    runtime_dir: Path | None = None
    _active_manifest: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.runtime_dir is None:
            self.runtime_dir = Path(tempfile.mkdtemp(prefix="confidencial-rag-"))
        else:
            self.runtime_dir = Path(self.runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def start(self) -> SystemState:
        with self._lock:
            self._require(SystemState.OFF)
            self.state = SystemState.STARTING
            self.state = SystemState.EMPTY
            return self.state

    def create_knowledge_base(self, name: str) -> dict[str, Any]:
        """Create and activate a content-free synthetic manifest."""
        with self._lock:
            self._require_any(SystemState.EMPTY, SystemState.READY)
            clean_name = self._validate_name(name)
            path = self._manifest_path(clean_name)
            if path.exists():
                raise KnowledgeBaseError(f"Knowledge base '{clean_name}' already exists.")
            self.state = SystemState.INDEXING
            manifest = {
                "name": clean_name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "document_count": 0,
                "status": "ready",
            }
            self._write_manifest(path, manifest)
            self._activate(manifest)
            return dict(manifest)

    def load_knowledge_base(self, name: str) -> dict[str, Any]:
        """Load and activate a synthetic manifest from this temporary runtime."""
        with self._lock:
            self._require_any(SystemState.EMPTY, SystemState.READY)
            clean_name = self._validate_name(name)
            path = self._manifest_path(clean_name)
            if not path.is_file():
                raise KnowledgeBaseError(f"Knowledge base '{clean_name}' was not found.")
            previous_state = self.state
            self.state = SystemState.LOADING
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
                self._validate_manifest(manifest, clean_name)
            except (OSError, json.JSONDecodeError, KnowledgeBaseError) as exc:
                self.state = previous_state
                if isinstance(exc, KnowledgeBaseError):
                    raise
                raise KnowledgeBaseError("The synthetic manifest could not be loaded.") from None
            self._activate(manifest)
            return dict(manifest)

    def save_knowledge_base(self) -> Path:
        """Save the active synthetic manifest to the temporary runtime."""
        with self._lock:
            self._require(SystemState.READY)
            if self.active_knowledge_base is None or self._active_manifest is None:
                raise KnowledgeBaseError("Saving requires an active knowledge base.")
            self.state = SystemState.SAVING
            path = self._manifest_path(self.active_knowledge_base)
            self._write_manifest(path, self._active_manifest)
            self.state = SystemState.READY
            return path

    def mock_chat(self, question: str) -> str:
        """Return a placeholder answer without retrieval or external model access."""
        with self._lock:
            self._require(SystemState.READY)
            if not question.strip():
                raise KnowledgeBaseError("Enter a question before sending.")
            self.state = SystemState.CHATTING
            self.state = SystemState.READY
            return (
                "Mock answer only: retrieval and the LLM are not implemented yet. "
                "No document content was accessed or sent externally."
            )

    def mark_ready(self, knowledge_base_name: str) -> SystemState:
        """Compatibility transition used by service integrations and early tests."""
        with self._lock:
            if self.state not in {SystemState.EMPTY, SystemState.LOADING}:
                raise InvalidStateTransition(
                    f"Cannot activate a knowledge base while state is {self.state}."
                )
            self.active_knowledge_base = knowledge_base_name
            self.state = SystemState.READY
            return self.state

    def shutdown(self) -> SystemState:
        with self._lock:
            if self.state is SystemState.OFF:
                return self.state
            self.state = SystemState.SHUTTING_DOWN
            self.active_knowledge_base = None
            self._active_manifest = None
            self.state = SystemState.OFF
            return self.state

    def _activate(self, manifest: dict[str, Any]) -> None:
        self._active_manifest = dict(manifest)
        self.active_knowledge_base = str(manifest["name"])
        self.state = SystemState.READY

    def _write_manifest(self, path: Path, manifest: dict[str, Any]) -> None:
        try:
            path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        except OSError:
            self.state = SystemState.ERROR
            raise KnowledgeBaseError("The synthetic manifest could not be saved.") from None

    def _manifest_path(self, name: str) -> Path:
        assert self.runtime_dir is not None
        return self.runtime_dir / f"{name}.json"

    @staticmethod
    def _validate_name(name: str) -> str:
        clean_name = name.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", clean_name):
            raise KnowledgeBaseError(
                "Use 1-64 letters, numbers, hyphens, or underscores; start with a letter or number."
            )
        return clean_name

    @staticmethod
    def _validate_manifest(manifest: Any, expected_name: str) -> None:
        if not isinstance(manifest, dict) or manifest.get("name") != expected_name:
            raise KnowledgeBaseError("The synthetic manifest is invalid.")
        if manifest.get("document_count") != 0 or manifest.get("status") != "ready":
            raise KnowledgeBaseError("The synthetic manifest is invalid.")

    def _require(self, required: SystemState) -> None:
        if self.state is not required:
            raise InvalidStateTransition(
                f"Operation requires state {required}; current state is {self.state}."
            )

    def _require_any(self, *allowed: SystemState) -> None:
        if self.state not in allowed:
            choices = ", ".join(str(state) for state in allowed)
            raise InvalidStateTransition(
                f"Operation requires one of ({choices}); current state is {self.state}."
            )
