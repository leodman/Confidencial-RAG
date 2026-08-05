# Security Policy

Confidencial RAG Version 1 is an experimental local-first RAG application. It is not production security, not a replacement for formal data-loss-prevention tooling, and not a guarantee that every confidential value will be detected or protected.

## Public repository assumptions

This repository must contain only source code, documentation, configuration examples, and synthetic text fixtures. Do not commit real customer data, confidential documents, notebook outputs, generated archives, vector indexes, model files, databases, screenshots, PDFs, DOCX files, ZIP packages, `.npy`/`.npz` files, or other generated binary artifacts.

## Prohibited confidential content

Do not place secrets or protected business data in issues, pull requests, tests, example files, documentation, comments, logs, or screenshots. Use obviously fictional synthetic data for examples and vulnerability reports.

## API keys and credentials

API keys, Gradio usernames/passwords, notebook credentials, and provider tokens must be entered only at runtime. They must not be committed, printed, logged, exported in knowledge-base packages, stored in configuration files, or embedded in notebook output.

## Runtime-only secrets

Version 1 keeps external-provider credentials and privacy token vaults in memory only. Safe shutdown clears active knowledge-base state, provider instances containing keys, token vaults/privacy sessions, temporary upload references, and staging directories.

## External LLM trust boundary

The external LLM is outside the trusted boundary. In `External, confidential` mode, retrieval happens locally first, selected context is sanitized locally with one shared privacy session, the outbound payload is validated for leakage, and only sanitized question/context/citation labels are sent. If sanitization or validation fails, the external call fails closed and is not retried with raw content.

## Token-vault handling

The token vault maps placeholders such as `<EMAIL_0001>` to original values. The vault is local, runtime-only, not displayed, not logged, not exported, and never sent to an external provider. Restoration is performed locally after external generation returns.

## Safe logging and errors

Logs and user-facing errors should include operational metadata such as counts, states, and safe exception categories. They must not include raw document text, raw questions, retrieved chunks, protected values, API keys, token mappings, local confidential filenames where avoidable, stack traces, or staging paths.

## Gradio shared URL exposure

A Colab `share=True` Gradio URL is internet-accessible to anyone who has the URL. Temporary username/password authentication reduces exposure but does not make the tunnel private infrastructure. Use temporary credentials and shut down the app when finished.

## Colab trust assumptions

Colab runtimes, uploaded files, downloaded archives, package caches, and browser sessions remain part of the user's trust model. Do not upload real confidential material unless you have independently accepted those risks.

## Knowledge-base exports

Version 1 knowledge-base ZIP exports are portable but unencrypted. They include extracted chunk text and local vectors. Protect downloaded archives as sensitive data and delete them when no longer needed.

## Vulnerability reporting

Report suspected vulnerabilities with synthetic examples only. Do not include real secrets, real customer documents, raw token-vault contents, or live API keys in reports.
