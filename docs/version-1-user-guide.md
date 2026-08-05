# Version 1 user guide

1. Open the Colab notebook from the README badge.
2. Run cells top to bottom.
3. Approve creation of a temporary Gradio shared URL.
4. Enter a temporary username and password.
5. Open the authenticated Gradio page.
6. Click **Start System**.
7. Create or import a knowledge base.
8. Upload supported files (`.txt`, `.md`, `.qmd`, `.html`, `.json`, `.csv`, extractable `.pdf`, `.docx`, or safe `.zip`). OCR is not implemented.
9. Index documents.
10. Ask questions in Local only mode or optional external modes.
11. Inspect answer citations, retrieved evidence, privacy report, and sanitized preview.
12. Export the knowledge base ZIP.
13. Use Safe Shutdown.

Limitations: detection can miss sensitive values, only external LLM payloads are sanitized, archives are not encrypted, and Colab plus downloaded files remain trusted by the user.
