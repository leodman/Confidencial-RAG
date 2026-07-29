"""Application lifecycle states.

The controller is intentionally strict: operations should validate the current
state before touching storage, documents, models, or external providers.
"""

from enum import StrEnum


class SystemState(StrEnum):
    """Supported high-level runtime states."""

    OFF = "off"
    STARTING = "starting"
    EMPTY = "empty"
    LOADING = "loading"
    READY = "ready"
    INDEXING = "indexing"
    CHATTING = "chatting"
    SAVING = "saving"
    SHUTTING_DOWN = "shutting_down"
    ERROR = "error"
