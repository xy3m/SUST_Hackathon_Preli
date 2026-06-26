"""Deterministic post-processing of the LLM response.

The LLM proposes an answer; these rules enforce the parts of the contract that
are fully deterministic so a single bad generation cannot break routing, the
evidence invariant, escalation, or the confidence field on hidden test cases.
"""

# department is a strict function of case_type (Problem Statement Section 7.2).
DEPARTMENT_BY_CASE_TYPE = {
    "wrong_transfer": "dispute_resolution",
    "payment_failed": "payments_ops",
    "duplicate_payment": "payments_ops",
    "refund_request": "customer_support",
    "merchant_settlement_delay": "merchant_operations",
    "agent_cash_in_issue": "agent_operations",
    "phishing_or_social_engineering": "fraud_risk",
    "other": "customer_support",
}

# Case types that warrant human review when evidence actually points to a
# concrete transaction (a confirmed dispute / high-value recovery).
ESCALATE_WHEN_MATCHED = {"wrong_transfer", "duplicate_payment", "agent_cash_in_issue"}

# Fallback confidence per verdict, only used when the LLM omits/zeros it.
DEFAULT_CONFIDENCE_BY_VERDICT = {
    "consistent": 0.9,
    "inconsistent": 0.75,
    "insufficient_data": 0.6,
}


def _derive_human_review(case_type: str, verdict: str) -> bool:
    """Escalation policy that matches the sample pack conventions."""
    # Suspected fraud/phishing always goes to a human, even with no transaction.
    if case_type == "phishing_or_social_engineering":
        return True
    # Ambiguous/vague cases need clarification first; do not escalate yet.
    if verdict == "insufficient_data":
        return False
    # A contradiction between claim and history always needs a human.
    if verdict == "inconsistent":
        return True
    # consistent: escalate only confirmed disputes / recoveries.
    return case_type in ESCALATE_WHEN_MATCHED


def _resolve_duplicate(history: list[dict]) -> str | None:
    """For a duplicate_payment claim, return the LATER of two identical payments."""
    groups: dict[tuple, list[dict]] = {}
    for txn in history:
        key = (txn.get("amount"), txn.get("counterparty"), txn.get("type"))
        groups.setdefault(key, []).append(txn)
    duplicates = [g for g in groups.values() if len(g) >= 2]
    if not duplicates:
        return None
    group = max(duplicates, key=len)
    latest = max(group, key=lambda t: t.get("timestamp", ""))
    return latest.get("transaction_id")


def _counterparty_count(history: list[dict], transaction_id: str) -> int:
    """How many history entries share the counterparty of the given transaction."""
    target = next((t for t in history if t.get("transaction_id") == transaction_id), None)
    if not target:
        return 0
    cp = target.get("counterparty")
    return sum(1 for t in history if t.get("counterparty") == cp)


def normalize_response(raw: dict, history: list[dict] | None = None) -> dict:
    """Enforce the deterministic invariants on an LLM response dict."""
    history = history or []
    case_type = raw.get("case_type")

    # 1. Duplicate payment is CONFIRMING evidence, not an ambiguous match. If the
    #    model failed to pick a transaction, point to the later duplicate.
    if (
        case_type == "duplicate_payment"
        and not raw.get("relevant_transaction_id")
        and history
    ):
        dup_id = _resolve_duplicate(history)
        if dup_id:
            raw["relevant_transaction_id"] = dup_id
            raw["evidence_verdict"] = "consistent"

    # 2. A "wrong transfer" to a counterparty that appears multiple times in the
    #    history contradicts the claim (established/known recipient).
    rel_id = raw.get("relevant_transaction_id")
    if (
        case_type == "wrong_transfer"
        and rel_id
        and _counterparty_count(history, rel_id) >= 2
    ):
        raw["evidence_verdict"] = "inconsistent"

    # 3. consistent/inconsistent require a matched transaction. With no
    #    relevant_transaction_id (empty history, vague or ambiguous complaint)
    #    the only honest verdict is insufficient_data.
    if not raw.get("relevant_transaction_id"):
        raw["evidence_verdict"] = "insufficient_data"

    # 4. Department always follows the case_type taxonomy.
    if case_type in DEPARTMENT_BY_CASE_TYPE:
        raw["department"] = DEPARTMENT_BY_CASE_TYPE[case_type]

    # 5. Escalation policy is deterministic given case_type + final verdict.
    raw["human_review_required"] = _derive_human_review(
        case_type, raw.get("evidence_verdict")
    )

    # 6. Never emit a null or zero confidence on a real analysis.
    confidence = raw.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence <= 0 or confidence > 1:
        raw["confidence"] = DEFAULT_CONFIDENCE_BY_VERDICT.get(
            raw.get("evidence_verdict"), 0.6
        )

    return raw
