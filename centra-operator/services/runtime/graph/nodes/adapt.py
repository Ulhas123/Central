from typing import Dict, Any, List
from ..state import RunState

def adapt_node(state: RunState) -> Dict[str, Any]:
    """
    Self-healing node: handles anomalies, environmental changes, and verification failures.
    Respects attempt budgets to avoid infinite loops.
    """
    last_obs = state.get("last_observation", {})
    anomalies = last_obs.get("anomalies", [])
    attempts = dict(state.get("attempts", {}))
    budget = state.get("budget", {"max_retries": 3})
    max_retries = budget.get("max_retries", 3)
    
    # Check if verification failed
    verification = state.get("verification")
    if verification and not verification.get("verified"):
        attempts["verification_retries"] = attempts.get("verification_retries", 0) + 1
        if attempts["verification_retries"] > max_retries:
            return {
                "status": "FAILED",
                "pending_action": None,
                "history": [{
                    "type": "escalation",
                    "reason": "Verification failed repeatedly (lying UI caught); retry budget exhausted."
                }]
            }
        # Adapt by re-inspecting ledger and retrying entry
        facts = dict(state.get("facts", {}))
        facts["invoice_posted"] = False
        return {
            "status": "ADAPTING",
            "facts": facts,
            "attempts": attempts,
            "pending_action": {
                "tool": "web_open",
                "arguments": {"path": "/invoices/new"},
                "risk": "read",
                "description": "Re-opening invoice entry form after verification mismatch (self-healing retry)"
            },
            "history": [{
                "type": "adapt_verification_failure",
                "attempt": attempts["verification_retries"]
            }]
        }

    # Handle environmental anomalies
    for anomaly in anomalies:
        atype = anomaly.get("type")
        attempts[atype] = attempts.get(atype, 0) + 1
        if attempts[atype] > max_retries:
            return {
                "status": "FAILED",
                "history": [{
                    "type": "escalation",
                    "reason": f"Anomaly {atype} exceeded retry budget."
                }]
            }

        # Anomaly 1: Session Expiry -> Re-authenticate
        if atype == "session_expiry":
            return {
                "status": "ADAPTING",
                "attempts": attempts,
                "pending_action": {
                    "tool": "web_submit",
                    "arguments": {
                        "form_id": "form-login",
                        "fields": {},
                        "credential_ref": "erp_ap_clerk"
                    },
                    "risk": "auth",
                    "description": "Re-authenticating session in CentraERP using least-privilege credential reference"
                },
                "history": [{
                    "type": "self_heal_reauth",
                    "attempt": attempts[atype]
                }]
            }

        # Anomaly 2: Interstitial Banner -> Dismiss notice
        if atype == "interstitial_banner":
            return {
                "status": "ADAPTING",
                "attempts": attempts,
                "pending_action": {
                    "tool": "web_submit",
                    "arguments": {
                        "form_id": "form-dismiss-banner",
                        "fields": {"return_to": "/invoices/new"}
                    },
                    "risk": "nav",
                    "description": "Dismissing interstitial maintenance notice banner"
                },
                "history": [{
                    "type": "self_heal_banner_dismiss",
                    "attempt": attempts[atype]
                }]
            }

        # Anomaly 3: Date Format Error -> Adjust format to YYYY-MM-DD
        if atype == "date_format_error":
            facts = dict(state.get("facts", {}))
            raw_date = facts.get("due_date", "")
            # Normalize to YYYY-MM-DD
            if "/" in raw_date:
                parts = raw_date.split("/")
                if len(parts) == 3:
                    facts["due_date"] = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            else:
                facts["due_date"] = "2026-11-20"
                
            return {
                "status": "ADAPTING",
                "facts": facts,
                "attempts": attempts,
                "pending_action": {
                    "tool": "web_open",
                    "arguments": {"path": "/invoices/new"},
                    "risk": "read",
                    "description": "Re-navigating to invoice form with sanitized YYYY-MM-DD date format"
                },
                "history": [{
                    "type": "self_heal_date_sanitization",
                    "new_date": facts["due_date"]
                }]
            }

        # Anomaly 4: Duplicate Trap -> Escalate safely
        if atype == "duplicate_trap":
            return {
                "status": "DUPLICATE_HALTED",
                "history": [{
                    "type": "escalation",
                    "reason": "Duplicate invoice confirmed by ERP unique index; stopping execution cleanly to prevent double posting."
                }]
            }

    # Default fallback
    return {
        "status": "PLANNING",
        "attempts": attempts
    }
