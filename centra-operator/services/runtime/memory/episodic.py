import time
from typing import List, Dict, Any, Optional
from .sops import compute_cosine_similarity, tokenize_and_embed

class EpisodicMemoryStore:
    """
    Episodic memory that learns from past human approvals, rejections, and overrides.
    Allows the agent to cite prior institutional decisions in approval cards.
    """
    def __init__(self, qdrant_client: Any = None):
        self.qdrant_client = qdrant_client
        # In-memory episodic store initialized with historical organizational context
        self.episodes: List[Dict[str, Any]] = [
            {
                "id": "ep_hist_1",
                "vendor": "Acme Corporation",
                "amount": 4200.00,
                "action": "invoice_post",
                "decision": "APPROVED",
                "approver": "Finance Director",
                "reason": "Standard quarterly cloud infrastructure maintenance under contract",
                "timestamp": time.time() - 86400 * 45
            },
            {
                "id": "ep_hist_2",
                "vendor": "Apex Global Inc.",
                "amount": 16000.00,
                "action": "invoice_post",
                "decision": "APPROVED",
                "approver": "CFO",
                "reason": "Annual security appliance procurement approved per board resolution",
                "timestamp": time.time() - 86400 * 90
            }
        ]

    def record_decision(self, vendor: str, amount: float, action: str, decision: str, approver: str, reason: str, note: Optional[str] = None):
        episode = {
            "id": f"ep_{int(time.time() * 1000)}",
            "vendor": vendor,
            "amount": amount,
            "action": action,
            "decision": decision,
            "approver": approver,
            "reason": reason,
            "note": note or "",
            "timestamp": time.time()
        }
        self.episodes.append(episode)
        return episode

    def search_similar_cases(self, vendor: str, amount: float, action: str = "invoice_post", top_k: int = 3) -> List[Dict[str, Any]]:
        query_text = f"{vendor} {action} amount {amount}"
        query_vec = tokenize_and_embed(query_text)
        
        scored = []
        for ep in self.episodes:
            ep_text = f"{ep['vendor']} {ep['action']} amount {ep['amount']} {ep['reason']}"
            ep_vec = tokenize_and_embed(ep_text)
            sim = compute_cosine_similarity(query_vec, ep_vec)
            # Bonus similarity for exact vendor match
            if ep["vendor"].lower() == vendor.lower():
                sim += 0.5
            scored.append((sim, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]
