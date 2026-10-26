import re
from typing import Dict, Any, List

try:
    from graph.state import RunState
except (ImportError, ValueError):
    from ..state import RunState

def understand_node(state: RunState) -> Dict[str, Any]:
    """
    Translates user goal into structured objectives and initial machine-checkable criteria.
    Extracts explicit entities (vendor, target files, PO numbers) from natural language.
    """
    goal = state["goal"]
    facts = dict(state.get("facts", {}))
    
    # Extract known vendor names if mentioned
    vendor_match = re.search(r'\b(acme|apex|helios)\b', goal, re.IGNORECASE)
    if vendor_match:
        facts["target_vendor_hint"] = vendor_match.group(1).capitalize()

    # Determine intent type
    if "aging" in goal.lower() or "unpaid" in goal.lower() or "older than 30" in goal.lower():
        intent = "aging_review"
        criteria = [
            {
                "id": "c_aging_inspect",
                "desc": "Vendor unpaid invoices are queried through read-only API",
                "check": {
                    "tool": "api_get",
                    "args": {"path": "/api/invoices", "query": {"vendor": facts.get("target_vendor_hint", "Helios")}},
                    "assert": [{"path": "$count", "op": "gte", "value": 1}]
                }
            },
            {
                "id": "c_aging_flag",
                "desc": "Overdue invoices (>30 days) are flagged for supervisor review",
                "check": {
                    "tool": "api_get",
                    "args": {"path": "/api/invoices", "query": {"vendor": facts.get("target_vendor_hint", "Helios")}},
                    "assert": [{"path": "0.flagged_for_review", "op": "eq", "value": True}]
                }
            }
        ]
    else:
        intent = "invoice_processing"
        criteria = [
            {
                "id": "c_invoice_posted",
                "desc": "Invoice exists in ERP General Ledger with status POSTED and verified amount",
                "check": {
                    "tool": "api_get",
                    "args": {"path": "/api/invoices"},
                    "assert": [
                        {"path": "$count", "op": "gte", "value": 1},
                        {"path": "status", "op": "eq", "value": "POSTED"}
                    ]
                }
            }
        ]

    facts["intent"] = intent
    
    return {
        "status": "UNDERSTOOD",
        "facts": facts,
        "criteria": criteria,
        "history": [{
            "type": "understand",
            "intent": intent,
            "target_vendor": facts.get("target_vendor_hint")
        }]
    }
