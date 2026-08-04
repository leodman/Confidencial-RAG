# Privacy gateway

The local privacy gateway detects email, phone, IPv4, SSN-like values, credit-card-like values, API-key-like strings, UUIDs, sensitive query URLs, and user terms. Values become deterministic reversible tokens such as `<EMAIL_0001>` and are restored locally. Confidential external mode fails closed if sanitization/generation cannot complete. This is a best-effort Version 1 mechanism, not a guarantee that all sensitive information is found.
