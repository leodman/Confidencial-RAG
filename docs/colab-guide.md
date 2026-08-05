# Colab Guide

Open `colab/confidencial_rag_launcher.ipynb` from the README badge and run cells top to bottom. The notebook clones or fetches the selected `GIT_REF`, installs Version 1 extras with `sys.executable`, adds `src` to the active kernel, verifies imports, asks for explicit shared-URL consent, prompts for temporary Gradio credentials, and launches authenticated `share=True`.

`GIT_REF` defaults to `main` for the normal user workflow. For PR smoke testing, temporarily set `GIT_REF` near the top of the notebook to the PR branch name; the notebook fetches that ref, checks out `FETCH_HEAD` deterministically, and prints the checked-out commit SHA.

The shared URL is internet-accessible to anyone with the URL. Local-only mode requires no API key.

## Manual Colab smoke-test checklist

Do not claim this checklist is complete unless it has actually been run in Colab.

1. Open the Colab notebook from the PR branch or temporarily change the notebook clone target to the PR branch for testing.
2. Run all cells from a fresh runtime.
3. Confirm package installation and model loading complete.
4. Create temporary Gradio credentials.
5. Open the authenticated shared URL.
6. Start the system.
7. Create a knowledge base.
8. Upload a synthetic `.txt` or `.md` document.
9. Index the document.
10. Ask a known question and verify the cited evidence.
11. Export the knowledge base ZIP.
12. Download the ZIP.
13. Factory-reset or restart the Colab runtime.
14. Run the notebook again.
15. Import the exported ZIP.
16. Ask the same question without re-indexing.
17. Verify the expected document and citation are returned.
18. Perform Safe Shutdown.
