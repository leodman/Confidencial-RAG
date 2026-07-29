"""Gradio application shell backed exclusively by ``ApplicationController``."""

from __future__ import annotations

from typing import Any

from ..controller import ApplicationController, InvalidStateTransition, KnowledgeBaseError


class UIActions:
    """Small callback adapter that converts controller exceptions into UI messages."""

    def __init__(self, controller: ApplicationController) -> None:
        self.controller = controller

    def snapshot(self, message: str) -> tuple[str, str, str]:
        return (
            self.controller.state.value.upper(),
            self.controller.active_knowledge_base or "None",
            message,
        )

    def _run(self, action: Any, success: str) -> tuple[str, str, str]:
        try:
            action()
            return self.snapshot(f"Success: {success}")
        except (InvalidStateTransition, KnowledgeBaseError) as exc:
            return self.snapshot(f"Error: {exc}")

    def start(self) -> tuple[str, str, str]:
        return self._run(self.controller.start, "System started.")

    def shutdown(self) -> tuple[str, str, str]:
        return self._run(self.controller.shutdown, "System shut down safely.")

    def create(self, name: str) -> tuple[str, str, str]:
        return self._run(
            lambda: self.controller.create_knowledge_base(name),
            f"Knowledge base '{name.strip()}' created.",
        )

    def load(self, name: str) -> tuple[str, str, str]:
        return self._run(
            lambda: self.controller.load_knowledge_base(name),
            f"Knowledge base '{name.strip()}' loaded.",
        )

    def save(self) -> tuple[str, str, str]:
        return self._run(self.controller.save_knowledge_base, "Knowledge base manifest saved.")

    def chat(self, question: str) -> tuple[str, str, str, str]:
        try:
            answer = self.controller.mock_chat(question)
            state, active, _ = self.snapshot("")
            return answer, state, active, "Success: Mock answer generated locally."
        except (InvalidStateTransition, KnowledgeBaseError) as exc:
            state, active, _ = self.snapshot("")
            return "", state, active, f"Error: {exc}"


def build_interface(controller: ApplicationController | None = None):
    """Build the Gradio Blocks interface without starting a web server."""
    import gradio as gr

    actions = UIActions(controller or ApplicationController())
    initial_state, initial_kb, initial_status = actions.snapshot("System is off.")

    with gr.Blocks(title="Confidencial RAG") as app:
        gr.Markdown(
            "# Confidencial RAG — application shell\n"
            "This milestone uses synthetic manifests and mock chat only; it is not a functional RAG."
        )
        with gr.Tab("System"):
            state_display = gr.Textbox(
                label="Current system state", value=initial_state, interactive=False
            )
            kb_display = gr.Textbox(
                label="Active knowledge base", value=initial_kb, interactive=False
            )
            start_button = gr.Button("Start System", variant="primary")
            shutdown_button = gr.Button("Safe Shutdown")

        with gr.Tab("Knowledge Base"):
            kb_name = gr.Textbox(label="Knowledge-base name", placeholder="test-kb")
            create_button = gr.Button("Create")
            load_button = gr.Button("Load")
            save_button = gr.Button("Save")
            status_display = gr.Textbox(
                label="Operation status", value=initial_status, interactive=False
            )

        with gr.Tab("Chat"):
            question = gr.Textbox(label="Question")
            send_button = gr.Button("Send", variant="primary")
            answer = gr.Textbox(label="Mock answer", interactive=False)

        common_outputs = [state_display, kb_display, status_display]
        start_button.click(actions.start, outputs=common_outputs)
        shutdown_button.click(actions.shutdown, outputs=common_outputs)
        create_button.click(actions.create, inputs=kb_name, outputs=common_outputs)
        load_button.click(actions.load, inputs=kb_name, outputs=common_outputs)
        save_button.click(actions.save, outputs=common_outputs)
        send_button.click(
            actions.chat,
            inputs=question,
            outputs=[answer, state_display, kb_display, status_display],
        )

    return app


def launch(*, share: bool = False, username: str | None = None, password: str | None = None):
    """Launch Gradio locally or through an authenticated shared URL.

    ``share=False`` is the safe default for localhost use on Windows, Linux, and
    macOS. Google Colab cannot expose that localhost page to the user's browser,
    so its launcher explicitly opts in to ``share=True`` and supplies both
    credentials. A Gradio shared URL should be treated as internet-accessible.
    """
    if share and (not username or not password):
        raise ValueError("A username and password are required when sharing is enabled.")
    auth = (username, password) if username and password else None
    return build_interface().launch(share=share, auth=auth)


if __name__ == "__main__":
    launch()
