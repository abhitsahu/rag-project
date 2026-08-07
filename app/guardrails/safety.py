"""Deterministic safety checks for data that must not leave the application.

These checks run before the LLM-based NeMo rails so a detected credential or PII
value is never sent to Groq, Qdrant, Portkey, or application telemetry.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SensitiveDataFinding:
    """A safe-to-log description of a detected sensitive-data category."""

    category: str
    message: str


_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----", re.IGNORECASE)
_AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_GITHUB_TOKEN = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")
_OPENAI_STYLE_KEY = re.compile(r"\b(?:sk|pk|gsk)_[A-Za-z0-9_-]{16,}\b", re.IGNORECASE)
_BEARER_TOKEN = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}\b", re.IGNORECASE)
_CREDENTIAL_ASSIGNMENT = re.compile(
    r"\b(?:api[_ -]?key|access[_ -]?key|secret(?:[_ -]?key)?|password|token|credentials?)"
    r"\s*(?:=|:|is)\s*['\"]?[^\s'\"]{8,}",
    re.IGNORECASE,
)
_SECRET_REQUEST = re.compile(
    r"\b(?:show|give|reveal|list|share|send|dump|print|expose|extract)\b.{0,80}"
    r"\b(?:api[_ -]?keys?|passwords?|secrets?|tokens?|credentials?|private[_ -]?keys?)\b",
    re.IGNORECASE,
)

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{8,}\d)(?!\w)")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
_AADHAAR = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
_CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")


def _looks_like_card_number(value: str) -> bool:
    """Use the Luhn check to avoid treating arbitrary long numbers as cards."""
    digits = "".join(character for character in value if character.isdigit())
    if not 13 <= len(digits) <= 19:
        return False

    total = 0
    for index, character in enumerate(reversed(digits)):
        number = int(character)
        if index % 2:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


def find_sensitive_data(text: str | None) -> SensitiveDataFinding | None:
    """Return the first sensitive-data category found without exposing its value."""
    if not text:
        return None

    credential_patterns = (
        _PRIVATE_KEY,
        _AWS_ACCESS_KEY,
        _GITHUB_TOKEN,
        _OPENAI_STYLE_KEY,
        _BEARER_TOKEN,
        _CREDENTIAL_ASSIGNMENT,
        _SECRET_REQUEST,
    )
    if any(pattern.search(text) for pattern in credential_patterns):
        return SensitiveDataFinding(
            category="confidential data",
            message=(
                "I can't process or disclose credentials, secrets, private keys, "
                "or other confidential access data. Please remove it and ask a "
                "general technical question instead."
            ),
        )

    if _EMAIL.search(text):
        return SensitiveDataFinding(
            category="personal data",
            message=(
                "I can't process personal data such as email addresses. Please "
                "remove personal information and try again."
            ),
        )

    if _PAN.search(text) or _AADHAAR.search(text) or any(
        _looks_like_card_number(match.group()) for match in _CARD_CANDIDATE.finditer(text)
    ):
        return SensitiveDataFinding(
            category="personal data",
            message=(
                "I can't process government ID or payment-card information. Please "
                "remove personal information and try again."
            ),
        )

    phone_match = _PHONE.search(text)
    if phone_match and 10 <= sum(character.isdigit() for character in phone_match.group()) <= 15:
        return SensitiveDataFinding(
            category="personal data",
            message=(
                "I can't process phone numbers. Please remove personal information "
                "and try again."
            ),
        )

    return None


def validate_output(text: str | None) -> tuple[bool, str | None]:
    """Reject an answer that appears to expose confidential data or PII."""
    finding = find_sensitive_data(text)
    if finding:
        return False, (
            "I can't return that response because it may contain "
            f"{finding.category}. Please use redacted, non-sensitive information."
        )
    return True, text
