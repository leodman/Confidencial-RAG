from confidencial_rag.controller import ApplicationController
from confidencial_rag.state import SystemState


def test_basic_lifecycle() -> None:
    controller = ApplicationController()

    assert controller.state is SystemState.OFF
    assert controller.start() is SystemState.EMPTY
    assert controller.mark_ready("synthetic-test-kb") is SystemState.READY
    assert controller.active_knowledge_base == "synthetic-test-kb"
    assert controller.shutdown() is SystemState.OFF
    assert controller.active_knowledge_base is None
