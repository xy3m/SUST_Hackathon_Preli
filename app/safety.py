import re

REFUND_PROMISE_PATTERNS = [
    r"\bwe (will|have) refund(ed)?\b",
    r"\byour money (has been|will be) (returned|refunded)\b",
    r"\bguarantee[d]? (a )?refund\b",
]

CREDENTIAL_REQUEST_PATTERNS = [
    r"\b(share|send|provide|enter) your (pin|otp|password|card number|cvv)\b",
    r"\bwhat is your (pin|otp|password)\b",
]

THIRD_PARTY_PATTERNS = [
    r"\bcontact (this number|the agent directly|0?1\d{9})\b",
]

# Negation cues that turn a credential phrase into a SAFE defensive warning,
# e.g. "do NOT share your PIN". We are explicitly allowed (and encouraged) to
# warn customers not to share credentials, so these must not count as violations.
NEGATION_RE = re.compile(
    r"\b(do not|don't|does not|doesn't|never|not|avoid|refrain|without|no one|nobody)\b",
    re.IGNORECASE,
)

SAFE_FALLBACK_REPLY = (
    "We have noted your concern and logged ticket {ticket_id}. Our support "
    "team will review the case and contact you through official channels. "
    "Please do not share your PIN, OTP, or password with anyone."
)

def _is_defensive_warning(text: str, match_start: int) -> bool:
    """True if a credential phrase is preceded by a negation (a safe warning)."""
    window = text[max(0, match_start - 30):match_start]
    return bool(NEGATION_RE.search(window))

def enforce_safety(response: dict) -> tuple[dict, list[str]]:
    """Applies rule-based safety filters to the LLM response."""
    violations = []

    # Check customer_reply and recommended_next_action
    for field in ("customer_reply", "recommended_next_action"):
        text = response.get(field, "") or ""
        # Refund promises and third-party redirects are violations in any context.
        for pat in REFUND_PROMISE_PATTERNS + THIRD_PARTY_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                violations.append(f"{field}:{pat}")
        # Credential mentions are violations only when the service is ASKING for
        # them, not when warning the customer NOT to share them.
        for pat in CREDENTIAL_REQUEST_PATTERNS:
            for m in re.finditer(pat, text, re.IGNORECASE):
                if not _is_defensive_warning(text, m.start()):
                    violations.append(f"{field}:{pat}")
                    break

    if violations:
        # Override with safe fallback reply
        response["customer_reply"] = SAFE_FALLBACK_REPLY.format(ticket_id=response.get("ticket_id", "unknown"))
        response["human_review_required"] = True
        response["reason_codes"] = (response.get("reason_codes") or []) + ["safety_override"]
        
    return response, violations
