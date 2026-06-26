import re
from datetime import datetime

def find_candidates(complaint: str, history: list[dict]) -> list[dict]:
    if not history:
        return []

    # 1. Extract potential amounts from the complaint
    # Match numbers that could be amounts (e.g., 5000, 1200.50)
    amount_matches = re.findall(r'\b\d+(?:\.\d+)?\b', complaint)
    complaint_amounts = [float(match) for match in amount_matches]

    # 2. Extract keywords for transaction types
    complaint_lower = complaint.lower()
    type_keywords = {
        "transfer": ["sent", "send", "transfer", "wrong number"],
        "payment": ["bill", "pay", "payment", "recharge", "merchant"],
        "cash_in": ["deposit", "cash in", "cash_in", "agent"],
        "cash_out": ["withdraw", "cash out", "cash_out"],
        "settlement": ["settlement", "sales", "settled"],
        "refund": ["refund", "returned"]
    }

    scored_history = []
    
    for idx, txn in enumerate(history):
        score = 0.0
        
        # A. Amount matching (±5%)
        txn_amount = float(txn.get("amount", 0.0))
        for camt in complaint_amounts:
            if camt > 0 and abs(txn_amount - camt) / camt <= 0.05:
                score += 50.0  # Strong signal
                break
                
        # B. Type matching based on keywords
        txn_type = txn.get("type", "")
        keywords = type_keywords.get(txn_type, [])
        if any(kw in complaint_lower for kw in keywords):
            score += 20.0
            
        # C. Recency matching
        # More recent transactions get a slight boost. We'll use the index since history 
        # is typically ordered most recent first, or we can parse the timestamp.
        try:
            # Add a small score based on recency to break ties (assuming standard ISO format)
            # We'll just give a small point boost, ensuring it doesn't override amount/type
            dt = datetime.fromisoformat(txn.get("timestamp", "").replace("Z", "+00:00"))
            score += dt.timestamp() / 1e10 # Tiny boost based on unix time
        except Exception:
            pass
            
        # D. Base order priority (if timestamps fail)
        score -= (idx * 0.1) 
        
        # Store scored candidate
        txn_copy = dict(txn)
        txn_copy["_heuristic_score"] = score
        scored_history.append(txn_copy)
        
    # Sort by score descending and return top 3
    scored_history.sort(key=lambda x: x["_heuristic_score"], reverse=True)
    return scored_history[:3]
