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

SAFE_FALLBACK_REPLY = (
    "We have noted your concern and logged ticket {ticket_id}. Our support "
    "team will review the case and contact you through official channels. "
    "Please do not share your PIN, OTP, or password with anyone."
)

def enforce_safety(response: dict) -> tuple[dict, list[str]]:
    """Applies rule-based safety filters to the LLM response."""
    violations = []
    
    # Check customer_reply and recommended_next_action
    for field in ("customer_reply", "recommended_next_action"):
        text = response.get(field, "") or ""
        for pat in REFUND_PROMISE_PATTERNS + CREDENTIAL_REQUEST_PATTERNS + THIRD_PARTY_PATTERNS:
            if re.search(pat, text, re.IGNORECASE):
                violations.append(f"{field}:{pat}")
                
    if violations:
        # Override with safe fallback reply
        response["customer_reply"] = SAFE_FALLBACK_REPLY.format(ticket_id=response.get("ticket_id", "unknown"))
        response["human_review_required"] = True
        response["reason_codes"] = (response.get("reason_codes") or []) + ["safety_override"]
        
    return response, violations
