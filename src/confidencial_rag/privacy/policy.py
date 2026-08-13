from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConfidentialityPolicy:
    """Configurable category decisions, separate from entity detection."""

    rules: dict[str, bool] = field(default_factory=lambda: {
        "PERSON": True,
        "EMAIL": True,
        "PHONE": True,
        "COMPANY": True,
        "ORGANIZATION": True,
        "INTERNAL_PROJECT": True,
        "PRODUCT": False,
        "TECHNOLOGY": False,
        # Existing structured protections remain enabled.
        "IP": True,
        "SSN": True,
        "CREDIT_CARD": True,
        "API_KEY": True,
        "UUID": True,
        "URL_SECRET": True,
    })

    def is_confidential(self, category: str) -> bool:
        return self.rules.get(category, False)


__all__ = ["ConfidentialityPolicy"]
