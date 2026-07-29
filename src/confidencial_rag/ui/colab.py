"""Testable Google Colab launch decision for the thin notebook."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .gradio_app import launch

COLAB_NOT_STARTED_MESSAGE = (
    "Application not started: Google Colab requires a temporary Gradio shared URL "
    "to make the browser interface reachable."
)


def launch_from_colab(
    enable_share: bool,
    *,
    username: str | None = None,
    password: str | None = None,
    launcher: Callable[..., Any] = launch,
) -> str:
    """Launch an authenticated Colab tunnel, or stop without starting the app.

    Unlike local execution, a Colab runtime's localhost page is not directly
    reachable from the user's browser. The notebook must therefore explicitly
    opt in to an internet-accessible Gradio shared URL protected by credentials.
    """
    if not enable_share:
        return COLAB_NOT_STARTED_MESSAGE
    if not username or not username.strip():
        raise ValueError("A non-empty username is required for the Colab shared URL.")
    if not password:
        raise ValueError("A non-empty password is required for the Colab shared URL.")

    launcher(share=True, username=username.strip(), password=password)
    return "Application started with an authenticated temporary Gradio shared URL."
