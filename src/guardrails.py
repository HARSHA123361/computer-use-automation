from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urlparse

from .schema import ActionType, RiskLevel, StepAction


ALLOWED_DOMAINS = [
    "127.0.0.1",
    "localhost",
]

ALLOWED_ACTION_TYPES = [
    ActionType.navigate,
    ActionType.click,
    ActionType.type_text,
    ActionType.select,
    ActionType.wait_for,
    ActionType.extract,
    ActionType.assert_checkpoint,
    ActionType.screenshot,
]

BLOCKED_URL_PATTERNS = [
    r".*\.(gov|mil)$",
    r".*bank.*\.com$",
    r".*creditunion.*\.com$",
]

PII_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]"),
    (r"\b\d{9}\b", "[SSN_REDACTED]"),
    (r"\b4[0-9]{12}(?:[0-9]{3})?\b", "[CARD_REDACTED]"),
    (r"\b5[1-5][0-9]{14}\b", "[CARD_REDACTED]"),
    (r"\b3[47][0-9]{13}\b", "[CARD_REDACTED]"),
    (r"(?i)password\s*[:=]\s*\S+", "[PASSWORD_REDACTED]"),
    (r"(?i)token\s*[:=]\s*\S+", "[TOKEN_REDACTED]"),
    (r"(?i)secret\s*[:=]\s*\S+", "[SECRET_REDACTED]"),
]

IRREVERSIBLE_STEP_ACTIONS = [
    "transfer",
    "submit",
    "confirm",
    "delete",
    "close account",
    "wire",
    "pay",
]


class PolicyViolation(Exception):
    pass


class GuardrailsEngine:
    def __init__(
        self,
        allowed_domains: Optional[List[str]] = None,
        require_confirmation_for_irreversible: bool = True,
    ):
        self.allowed_domains = allowed_domains or ALLOWED_DOMAINS
        self.require_confirmation_for_irreversible = require_confirmation_for_irreversible

    def check_url(self, url: str) -> None:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        if hostname not in self.allowed_domains:
            for pattern in BLOCKED_URL_PATTERNS:
                if re.match(pattern, hostname):
                    raise PolicyViolation(f"URL hostname '{hostname}' matches a blocked pattern.")
            if hostname not in self.allowed_domains:
                raise PolicyViolation(
                    f"URL hostname '{hostname}' is not in the allowed domain list: {self.allowed_domains}"
                )

    def check_action(self, step: StepAction) -> None:
        if step.action not in ALLOWED_ACTION_TYPES:
            raise PolicyViolation(f"Action type '{step.action}' is not in the allowed action list.")

        if step.risk == RiskLevel.irreversible and self.require_confirmation_for_irreversible:
            raise PolicyViolation(
                f"Step '{step.description}' is marked irreversible. "
                "Manual confirmation required before executing. "
                "Set require_confirmation_for_irreversible=False or approve the step explicitly."
            )

    def check_step_description(self, description: str) -> None:
        lower = description.lower()
        for keyword in IRREVERSIBLE_STEP_ACTIONS:
            if keyword in lower:
                pass

    def redact(self, text: str) -> str:
        result = text
        for pattern, replacement in PII_PATTERNS:
            result = re.sub(pattern, replacement, result)
        return result

    def redact_dict(self, data: dict) -> dict:
        cleaned = {}
        for key, value in data.items():
            if isinstance(value, str):
                cleaned[key] = self.redact(value)
            elif isinstance(value, dict):
                cleaned[key] = self.redact_dict(value)
            else:
                cleaned[key] = value
        return cleaned

    def is_safe_to_record(self, value: str) -> bool:
        for pattern, _ in PII_PATTERNS:
            if re.search(pattern, value):
                return False
        return True


guardrails = GuardrailsEngine()
