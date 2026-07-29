# Security Policy

## Public repository assumption

Treat every committed file, branch, pull request, issue, workflow log, and artifact in this repository as public. Git history is not a secure deletion mechanism.

## Prohibited repository content

Do not commit or upload:

- confidential, personal, regulated, or customer documents;
- API keys, passwords, access tokens, certificates, encryption keys, or recovery codes;
- original filenames or metadata that reveal confidential activity;
- vector stores, embeddings, metadata databases, token maps, or privacy vaults;
- exported knowledge bases, backups, caches, logs, debug traces, or notebook outputs containing real data.

Use synthetic fixtures for all public development and testing.

## Runtime secrets

Secrets must be entered at runtime using hidden input or an approved secret store. They should remain only in process memory where practical, must never be printed or included in exceptions, and must be cleared during safe shutdown.

## Trust boundary

The active Colab runtime, explicitly trusted connected storage, authenticated browser session, and local privacy components form the confidential processing environment. External LLM providers, public GitHub, and unauthenticated web clients are outside that boundary.

Only an outbound request approved by the privacy gateway and leakage checks may cross to an external LLM. The system must fail closed when sanitization cannot be verified.

A Colab-hosted web page is not inherently local. Shared or tunneled URLs must be authenticated, treated as internet-accessible, and disabled by default.

## Logging and errors

Default logs may contain identifiers, counts, timings, hashes, status values, and error codes. They must not contain raw document text, original questions, restored answers, confidential filenames, token maps, credentials, or full external payloads.

User-facing errors must not expose filesystem paths, secrets, raw document content, or internal token mappings.

## Backups

Knowledge-base exports containing confidential data must be encrypted before leaving the active runtime. Encryption keys and passwords must be stored separately from encrypted backups.

## Reporting vulnerabilities

Do not disclose vulnerabilities using real confidential data in a public issue. Contact the repository owner privately and provide a minimal reproduction using synthetic data.
