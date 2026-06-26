def safe_fallback(ticket_id: str) -> dict:
    """Returns a deterministic safe response if the primary analysis fails."""
    return {
        "ticket_id": ticket_id,
        "relevant_transaction_id": None,
        "evidence_verdict": "insufficient_data",
        "case_type": "other",
        "severity": "medium",
        "department": "customer_support",
        "agent_summary": "Automated analysis was unavailable for this ticket; manual review required.",
        "recommended_next_action": "Route to a human agent for manual investigation.",
        "customer_reply": "We have noted your concern and a support agent will review it shortly. Please do not share your PIN, OTP, or password with anyone.",
        "human_review_required": True,
        "confidence": 0.0,
        "reason_codes": ["llm_unavailable", "manual_fallback"],
    }
