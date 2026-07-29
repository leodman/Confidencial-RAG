import json

import pytest

from confidencial_rag.controller import (
    ApplicationController,
    InvalidStateTransition,
    KnowledgeBaseError,
)
from confidencial_rag.state import SystemState


def test_normal_lifecycle(tmp_path) -> None:
    controller = ApplicationController(runtime_dir=tmp_path)

    assert controller.state is SystemState.OFF
    assert controller.start() is SystemState.EMPTY
    manifest = controller.create_knowledge_base("synthetic-test-kb")
    assert manifest["document_count"] == 0
    assert controller.state is SystemState.READY
    assert controller.active_knowledge_base == "synthetic-test-kb"
    assert controller.shutdown() is SystemState.OFF
    assert controller.active_knowledge_base is None


@pytest.mark.parametrize("operation", ["create", "load", "save"])
def test_knowledge_base_operations_are_blocked_while_off(tmp_path, operation) -> None:
    controller = ApplicationController(runtime_dir=tmp_path)

    with pytest.raises(InvalidStateTransition):
        if operation == "create":
            controller.create_knowledge_base("test-kb")
        elif operation == "load":
            controller.load_knowledge_base("test-kb")
        else:
            controller.save_knowledge_base()


def test_start_cannot_run_twice(tmp_path) -> None:
    controller = ApplicationController(runtime_dir=tmp_path)
    controller.start()

    with pytest.raises(InvalidStateTransition):
        controller.start()


def test_create_writes_only_a_synthetic_manifest(tmp_path) -> None:
    controller = ApplicationController(runtime_dir=tmp_path)
    controller.start()
    controller.create_knowledge_base("test-kb")

    stored = json.loads((tmp_path / "test-kb.json").read_text(encoding="utf-8"))
    assert stored == {
        "name": "test-kb",
        "created_at": stored["created_at"],
        "document_count": 0,
        "status": "ready",
    }


def test_save_and_load_manifest(tmp_path) -> None:
    creator = ApplicationController(runtime_dir=tmp_path)
    creator.start()
    created = creator.create_knowledge_base("portable-kb")
    saved_path = creator.save_knowledge_base()

    loader = ApplicationController(runtime_dir=tmp_path)
    loader.start()
    loaded = loader.load_knowledge_base("portable-kb")

    assert saved_path == tmp_path / "portable-kb.json"
    assert loaded == created
    assert loader.active_knowledge_base == "portable-kb"
    assert loader.state is SystemState.READY


def test_save_requires_an_active_manifest(tmp_path) -> None:
    controller = ApplicationController(runtime_dir=tmp_path)
    controller.start()

    with pytest.raises(InvalidStateTransition):
        controller.save_knowledge_base()


def test_invalid_name_cannot_escape_runtime_directory(tmp_path) -> None:
    controller = ApplicationController(runtime_dir=tmp_path)
    controller.start()

    with pytest.raises(KnowledgeBaseError):
        controller.create_knowledge_base("../secret")


def test_mock_chat_is_blocked_while_off(tmp_path) -> None:
    controller = ApplicationController(runtime_dir=tmp_path)

    with pytest.raises(InvalidStateTransition):
        controller.mock_chat("What is indexed?")


def test_mock_chat_is_available_while_ready(tmp_path) -> None:
    controller = ApplicationController(runtime_dir=tmp_path)
    controller.start()
    controller.create_knowledge_base("test-kb")

    answer = controller.mock_chat("What is indexed?")

    assert "retrieval and the LLM are not implemented" in answer
    assert controller.state is SystemState.READY
