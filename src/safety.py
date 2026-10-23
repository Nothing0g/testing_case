"""Input safety, prompt-injection detection, and PII/payment-data redaction."""
from __future__ import annotations
import re
from dataclasses import dataclass

PHONE_RE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
CARD_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|system|safety) instructions",
    r"reveal (the )?(hidden )?(system )?prompt",
    r"show (me )?(customer )?(card|credit card) numbers?",
    r"print (the )?(full )?customer database",
    r"reveal (the )?hidden judge test cases",
    r"supplier contract prices?",
    r"bypass (the )?(safety|security|approval) rules",
    r"invent (a )?policy",
    r"show .*passwords?",
]

@dataclass
class SafetyResult:
    sanitized_text: str
    pii_masked: bool
    safety_refusal: bool
    reason: str | None

class SafetyAgent:
    def inspect(self, text: str) -> SafetyResult:
        original = text or ""
        lower = original.lower()
        injection = any(re.search(p, lower) for p in INJECTION_PATTERNS)
        # A card-number disclosure request is unsafe even if it does not include a number.
        restricted_intent = injection or any(x in lower for x in [
            "customer card numbers", "cvv", "pin numbers", "otp", "admin password",
            "supplier contract price", "supplier contract prices", "full customer database",
            "hidden judge test cases", "payment tokens", "pos credentials"
        ])
        sanitized = original
        # Replace valid payment-card-like values first so they are not partially masked as phones.
        def replace_card(match):
            digits = re.sub(r"\D", "", match.group(0))
            if len(digits) in range(13, 20):
                return "[REDACTED_CARD]"
            return match.group(0)
        sanitized = CARD_CANDIDATE_RE.sub(replace_card, sanitized)
        sanitized = EMAIL_RE.sub(lambda m: m.group(0)[0] + "*" * max(1, len(m.group(0).split("@")[0]) - 2) + m.group(0).split("@")[0][-1:] + "@" + m.group(0).split("@")[1], sanitized)
        sanitized = PHONE_RE.sub(lambda m: "******" + re.sub(r"\D", "", m.group(0))[-4:], sanitized)
        masked = sanitized != original
        reason = "Prompt-injection or restricted-data request" if restricted_intent else None
        return SafetyResult(sanitized, masked, restricted_intent, reason)
