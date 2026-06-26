import re

def find_candidates(complaint: str, history: list[dict]) -> list[dict]:
    """
    Light heuristic scoring — not the final answer, just a hint for the LLM.
    Score by: amount mentioned in complaint matches transaction.amount (±5%),
    type keywords ("sent"/"transfer", "bill"/"payment", "deposit"/"cash_in"),
    and recency (closer timestamp = higher score).
    Return the top 3 candidates with their scores attached.
    """
    if not history:
        return []

    # Extract potential amounts from the complaint using a simple regex
    # Matches numbers like 100, 100.50, 1,000, etc.
    amount_matches = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', complaint)
    amounts_in_complaint = []
    for match in amount_matches:
        try:
            amounts_in_complaint.append(float(match.replace(',', '')))
        except ValueError:
            pass

    # Keyword lists mapped to transaction types
    type_keywords = {
        "transfer": ["sent", "transfer", "send", "give", "paid", "wrong number"],
        "payment": ["bill", "payment", "merchant", "pay", "bought", "shop"],
        "cash_in": ["deposit", "cash in", "cash-in", "add money", "recharge"],
        "cash_out": ["withdraw", "cash out", "cash-out", "agent"],
        "settlement": ["settlement", "settle", "batch"],
        "refund": ["refund", "return", "back"]
    }
    
    complaint_lower = complaint.lower()
    
    scored_candidates = []
    for i, tx in enumerate(history):
        score = 0.0
        
        # 1. Amount match (highest weight)
        tx_amount = float(tx.get('amount', 0.0))
        for amt in amounts_in_complaint:
            # Check within ±5%
            if tx_amount > 0 and abs(amt - tx_amount) / tx_amount <= 0.05:
                score += 5.0
                break # Only score once for amount

        # 2. Type keyword match
        tx_type = tx.get('type', '')
        if tx_type in type_keywords:
            for kw in type_keywords[tx_type]:
                if kw in complaint_lower:
                    score += 2.0
                    break

        # 3. Recency
        # Assuming the history list is ordered newest first or similar, 
        # we give a small boost to earlier items in the list.
        recency_score = max(0, 1.0 - (i * 0.2))
        score += recency_score
        
        # Attach score
        tx_with_score = dict(tx) # shallow copy
        tx_with_score['_heuristic_score'] = score
        scored_candidates.append(tx_with_score)
        
    # Sort by score descending
    scored_candidates.sort(key=lambda x: x.get('_heuristic_score', 0), reverse=True)
    
    # Return top 3
    return scored_candidates[:3]
