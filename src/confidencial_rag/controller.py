"""Central application lifecycle controller."""

from dataclasses import dataclass, field
from threading import RLock

from .state import SystemState


class InvalidStateTransition(RuntimeError):
    """Raised when an operation is not valid in the current state."""


@dataclass
class ApplicationController:
    """Coordinate lifecycle operations without coupling the UI to modules.

    Concrete storage, ingestion, retrieval, privacy, and LLM services will be
    injected here as the project grows.
    """

    state: SystemState = SystemState.OFF
    active_knowledge_base: str | None = None
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def start(self) -> SystemState:
        with self._lock:
            self._require(SystemState.OFF)
            self.state = SystemState.STARTING
            self.state = SystemState.EMPTY
            return self.state

    def mark_ready(self, knowledge_base_name: str) -> SystemState:
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
            self.state = SystemState.OFF
            return self.state

    def _require(self, required: SystemState) -> None:
        if self.state is not required:
            raise InvalidStateTransition(
                f"Operation requires state {required}; current state is {self.state}."
            )
