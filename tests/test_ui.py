import pytest

from confidencial_rag.controller import ApplicationController
from confidencial_rag.ui.gradio_app import UIActions, launch


def test_callbacks_report_errors_instead_of_raising(tmp_path) -> None:
    actions = UIActions(ApplicationController(runtime_dir=tmp_path))

    state, active, message = actions.load("missing")

    assert state == "OFF"
    assert active == "None"
    assert message.startswith("Error:")


def test_shared_launch_requires_authentication() -> None:
    with pytest.raises(ValueError, match="username and password"):
        launch(share=True)
