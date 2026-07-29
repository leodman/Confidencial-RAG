import pytest

from confidencial_rag.controller import ApplicationController
from confidencial_rag.ui.colab import COLAB_NOT_STARTED_MESSAGE, launch_from_colab
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


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"share": False}, {"share": False, "auth": None}),
        (
            {"share": True, "username": "operator", "password": "runtime-password"},
            {"share": True, "auth": ("operator", "runtime-password")},
        ),
    ],
)
def test_launch_accepts_local_mode_and_authenticated_sharing(monkeypatch, kwargs, expected) -> None:
    received = {}

    class FakeInterface:
        def launch(self, **launch_kwargs):
            received.update(launch_kwargs)
            return "launched"

    monkeypatch.setattr(
        "confidencial_rag.ui.gradio_app.build_interface", lambda: FakeInterface()
    )

    assert launch(**kwargs) == "launched"
    assert received == expected


def test_colab_decline_does_not_launch() -> None:
    calls = []

    message = launch_from_colab(False, launcher=lambda **kwargs: calls.append(kwargs))

    assert message == COLAB_NOT_STARTED_MESSAGE
    assert calls == []


def test_colab_acceptance_launches_with_authentication() -> None:
    calls = []

    message = launch_from_colab(
        True,
        username=" operator ",
        password="runtime-password",
        launcher=lambda **kwargs: calls.append(kwargs),
    )

    assert "authenticated" in message
    assert calls == [
        {
            "share": True,
            "username": "operator",
            "password": "runtime-password",
        }
    ]
