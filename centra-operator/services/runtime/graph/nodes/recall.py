from typing import Dict, Any, List
from ..state import RunState
from ...memory.sops import SopMemoryStore
from ...memory.episodic import EpisodicMemoryStore

def recall_node(state: RunState, sop_store: SopMemoryStore, episodic_store: EpisodicMemoryStore) -> Dict[str, Any]:
    """
    Recalls organizational context:
    1. Semantic search for company Standard Operating Procedures (SOPs).
    2. Episodic search for past human decisions on similar cases.
    3. Merges mandatory policy checks into acceptance criteria.
    """
    goal = state["goal"]
    facts = state.get("facts", {})
    vendor_hint = facts.get("target_vendor_hint", "")
    
    # 1. Search SOPs
    search_query = f"{goal} {vendor_hint}"
    retrieved_sops = sop_store.search_sops(search_query, top_k=2)
    
    # 2. Search episodic memory
    amount_hint = facts.get("amount", 0.0)
    retrieved_memories = episodic_store.search_similar_cases(
        vendor=vendor_hint or "General",
        amount=amount_hint,
        action="invoice_post",
        top_k=2
    )

    # 3. Add mandatory policy checks to criteria
    criteria = list(state.get("criteria", []))
    for sop in retrieved_sops:
        for check in sop.get("required_checks", []):
            if not any(c.get("id") == check for c in criteria):
                criteria.append({
                    "id": check,
                    "desc": f"Mandatory policy check enforced by {sop['id']}: {check}",
                    "source_sop": sop["id"]
                })

    return {
        "status": "RECALLED",
        "policies": retrieved_sops,
        "memories": retrieved_memories,
        "criteria": criteria,
        "history": [{
            "type": "recall",
            "retrieved_sops": [s["id"] for s in retrieved_sops],
            "retrieved_memories_count": len(retrieved_memories)
        }]
    }
