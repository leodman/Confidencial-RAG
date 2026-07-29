# Confidencial RAG

A modular experiment intended to become a confidential Retrieval-Augmented Generation
system for temporary runtimes such as Google Colab.

> **Warning:** This application-shell milestone is **not yet a functional confidential
> RAG**. Do not use it with confidential data.

## What this milestone provides

- A strict `ApplicationController` lifecycle covering OFF, STARTING, EMPTY, LOADING,
  READY, INDEXING, CHATTING, SAVING, SHUTTING_DOWN, and ERROR states.
- A Gradio interface with system, synthetic knowledge-base, and mock-chat controls.
- Content-free JSON manifests stored only in a temporary runtime directory.
- A thin Colab launcher whose public sharing option is off by default and requires
  explicit authentication when enabled.
- Clear, non-crashing UI messages for expected invalid operations.

It deliberately does **not** implement document ingestion or parsing, embeddings, vector
search, real retrieval, privacy tokenization, encryption, external LLM calls, Google
Drive, or OneDrive. Mock chat explicitly reports these limitations and sends nothing to
an external service.

## Run locally

Python 3.10 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[ui]'
python -m confidencial_rag.ui.gradio_app
```

The local launcher uses `share=False`: Gradio's localhost mode is appropriate when the
browser and application run on the same Windows, Linux, or macOS computer. Local users
are not forced to create a public tunnel. Programmatic sharing requires both `username`
and `password`:

```python
from confidencial_rag.ui import launch
launch(share=True, username="choose-a-user", password="enter-at-runtime")
```

Never put credentials in source, notebooks, or runtime configuration committed to Git.
Use [`config/default.example.yaml`](config/default.example.yaml) only as the safe
configuration reference.

## Run from Google Colab

Open [`colab/confidencial_rag_launcher.ipynb`](colab/confidencial_rag_launcher.ipynb) in
Colab and run its cells. The notebook clones or fast-forward updates the repository,
installs the `ui` extra, and imports the packaged launcher. A Colab runtime's localhost
page is not directly reachable from the user's browser, so the browser UI requires a
temporary Gradio shared URL. The notebook asks explicitly whether to create that URL and
defaults to no. If declined, it reports that the application was not started and does not
call the launcher. If accepted, it requires a username and a hidden, non-empty password.

Treat the temporary URL as internet-accessible even though it is authenticated. Do not
share it, and use only synthetic data with this milestone. The notebook neither prints
nor persists the password, contains no application logic, and has no committed outputs.

## Architecture

Gradio is a presentation adapter: callbacks invoke the existing controller and never
access future storage, retrieval, privacy, encryption, or LLM components directly. The
controller owns lifecycle transitions and this milestone's temporary synthetic manifest.
The Colab notebook only bootstraps the package. See
[`docs/application-shell.md`](docs/application-shell.md) and
[`docs/system-overview.md`](docs/system-overview.md).

## Security boundary

This public repository contains source code, documentation, safe configuration templates,
tests, and synthetic examples only. Never commit secrets, real documents, embeddings,
vector databases, vaults, exports, runtime caches, or logs containing user content. See
[`SECURITY.md`](SECURITY.md) for the full policy.

## Development

```bash
python -m pip install -e '.[dev,ui]'
pytest
ruff check .
```

The project name uses the repository spelling **Confidencial RAG**. In English
documentation, the intended meaning is **Confidential RAG**.
