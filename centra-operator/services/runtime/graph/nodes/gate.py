from typing import Dict, Any, List, Optional

try:
    from graph.state import RunState
    from memory.episodic import EpisodicMemoryStore
except (ImportError, ValueError):
    from ..state import RunState
    from ...memory.episodic import EpisodicMemoryStore

def evaluate_rules(action: Dict[str, Any], facts: Dict[str, Any], policies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Evaluates policy rules deterministically against action and facts.
    """
    operation = action.get("operation")
    risk = action.get("risk", "read")
    
    # 1. Hard rule: Irreversible actions ALWAYS require human approval
    if risk == "irreversible":
        return {
            "needs_approval": True,
            "reason": "Action is classified as 'irreversible' per enterprise safety manifest",
            "policy_ids": ["manifest-safety-guardrail"]
        }

    # 2. Evaluate SOP rules against facts
    for policy in policies:
        rules = policy.get("rules", [])
        for rule in rules:
            if rule.get("applies_to") == operation:
                field = rule.get("field")
                op = rule.get("op")
                threshold = rule.get("value")
                fact_val = facts.get(field)
                
                if fact_val is not None:
                    triggered = False
                    if op == "gt" and float(fact_val) > float(threshold):
                        triggered = True
                    elif op == "gte" and float(fact_val) >= float(threshold):
                        triggered = True
                    elif op == "lt" and float(fact_val) < float(threshold):
                        triggered = True
                    elif op == "ne" and str(fact_val) != str(threshold):
                        triggered = True
                    elif op == "eq" and str(fact_val) == str(threshold):
                        triggered = True

                    if triggered and rule.get("action") == "require_approval":
                        return {
                            "needs_approval": True,
                            "reason": rule.get("reason", f"Rule violation on {field} {op} {threshold}"),
                            "policy_ids": [policy.get("id")]
                        }

    return {"needs_approval": False, "reason": None, "policy_ids": []}

def gate_node(state: RunState, episodic_store: EpisodicMemoryStore) -> Dict[str, Any]:
    """
    Gate node: deterministic policy guardrail enforcement.
    """
    action = state.get("pending_action")
    if not action:
        return {"status": "APPROVED_TO_ACT"}

    # If action was already approved via resume callback, proceed
    if state.get("status") == "AWAITING_APPROVAL":
        # Check if approval decision is already injected into facts
        human_decision = state.get("facts", {}).get("human_decision")
        if human_decision:
            if not human_decision.get("approved"):
                return {
                    "status": "REJECTED",
                    "history": [{
                        "type": "human_rejection",
                        "note": human_decision.get("note", "Rejected by manager")
                    }]
                }
            else:
                # Record approval into episodic memory
                facts = state.get("facts", {})
                episodic_store.record_decision(
                    vendor=facts.get("vendor", "General"),
                    amount=facts.get("amount", 0.0),
                    action=action.get("operation", "action"),
                    decision="APPROVED",
                    approver="Finance Manager",
                    reason="Managerial override via Dashboard Approval Card",
                    note=human_decision.get("note")
                )
                return {
                    "status": "APPROVED_TO_ACT",
                    "history": [{
                        "type": "human_approval_received",
                        "note": human_decision.get("note")
                    }]
                }

    # Evaluate deterministic policy rules
    decision = evaluate_rules(action, state.get("facts", {}), state.get("policies", []))

    if decision["needs_approval"]:
        interrupt_payload = {
            "action": action,
            "reason": decision["reason"],
            "policy_ids": decision["policy_ids"],
            "similar_past_cases": state.get("memories", [])[:3]
        }
        return {
            "status": "AWAITING_APPROVAL",
            "interrupt_data": interrupt_payload,
            "history": [{
                "type": "interrupt_requested",
                "reason": decision["reason"],
                "policy_ids": decision["policy_ids"]
            }]
        }

    return {"status": "APPROVED_TO_ACT"}
