# Privacy Gateway

The privacy gateway uses one request-scoped session and one in-memory vault for the outbound external-LLM request. The session sanitizes the question, selected context chunks, and citation labels/filenames; repeated values reuse a token and custom terms are processed longest-match-first.

Detected categories include email, phone, IPv4, SSN-like strings, credit-card-like strings, API-key-like strings, UUIDs, sensitive URLs, and custom terms. Detection is regex/user-input based and can miss values. The token vault is not logged, displayed, persisted, or sent externally.
