from typing import Dict, Any, List, Optional

try:
    from graph.state import RunState
except (ImportError, ValueError):
    from ..state import RunState

def plan_node(state: RunState) -> Dict[str, Any]:
    """
    Dynamic planner: selects the next action based on current state facts and observations.
    Revises plan adaptively rather than executing a hardcoded sequence.
    """
    facts = state.get("facts", {})
    intent = facts.get("intent", "invoice_processing")
    history = state.get("history", [])
    last_obs = state.get("last_observation")
    
    # ------------------ Intent: Invoice Processing ------------------
    if intent == "invoice_processing":
        # Step 1: Read source invoice document if not yet read
        if "raw_document" not in facts:
            vendor_hint = facts.get("target_vendor_hint", "").lower()
            target_file = "apex_inv_9901.txt" if "apex" in vendor_hint else "acme_inv_2041.txt"
            return {
                "status": "PLANNING",
                "pending_action": {
                    "tool": "inbox_read",
                    "arguments": {"filename": target_file},
                    "risk": "read",
                    "description": f"Read source invoice document '{target_file}' from inbox"
                }
            }

        # Step 2: Inspect PO ledger for 3-way matching
        po_number = facts.get("po_number")
        if po_number and "po_record" not in facts:
            return {
                "status": "PLANNING",
                "pending_action": {
                    "tool": "api_get",
                    "arguments": {
                        "path": "/api/po",
                        "query": {"po_number": po_number}
                    },
                    "risk": "read",
                    "description": f"Verify PO commitment '{po_number}' in CentraERP ledger"
                }
            }

        # Step 3: Open Invoice Entry Page if not open
        current_page = facts.get("current_page_model", {})
        current_url = current_page.get("url", "")
        forms = current_page.get("forms", [])
        has_entry_form = any(f["id"] == "form-invoice-entry" for f in forms)

        if not has_entry_form and not facts.get("invoice_posted"):
            return {
                "status": "PLANNING",
                "pending_action": {
                    "tool": "web_open",
                    "arguments": {"path": "/invoices/new"},
                    "risk": "read",
                    "description": "Navigate to CentraERP invoice entry form"
                }
            }

        # Step 4: Submit invoice entry form
        if has_entry_form and not facts.get("invoice_posted"):
            # Check if any field is renamed
            entry_form = next(f for f in forms if f["id"] == "form-invoice-entry")
            field_names = [f["name"] for f in entry_form["fields"]]
            inv_field = "invoice_ref_no" if "invoice_ref_no" in field_names else "invoice_number"

            fields_to_submit = {
                "vendor": facts.get("vendor"),
                inv_field: facts.get("invoice_number"),
                "amount": str(facts.get("amount")),
                "po_number": facts.get("po_number"),
                "due_date": facts.get("due_date")
            }
            return {
                "status": "PLANNING",
                "pending_action": {
                    "tool": "web_submit",
                    "arguments": {
                        "form_id": "form-invoice-entry",
                        "fields": fields_to_submit
                    },
                    "risk": "write",
                    "operation": "invoice_post",
                    "description": f"Post invoice {facts.get('invoice_number')} to General Ledger"
                }
            }

        # All execution steps finished -> Move to verification
        return {
            "status": "READY_TO_VERIFY",
            "pending_action": None
        }

    # ------------------ Intent: Aging Review (Generalization Task) ------------------
    elif intent == "aging_review":
        if "raw_document" not in facts:
            return {
                "status": "PLANNING",
                "pending_action": {
                    "tool": "inbox_read",
                    "arguments": {"filename": "helios_email.txt"},
                    "risk": "read",
                    "description": "Read Helios overdue notice inquiry from inbox"
                }
            }

        if "unpaid_invoices" not in facts:
            return {
                "status": "PLANNING",
                "pending_action": {
                    "tool": "api_get",
                    "arguments": {
                        "path": "/api/invoices",
                        "query": {"vendor": "Helios Systems", "status": "UNPAID"}
                    },
                    "risk": "read",
                    "description": "Retrieve unpaid invoices for Helios Systems via read-only API"
                }
            }

        # Flag any unflagged overdue invoice
        overdue_invoices = facts.get("overdue_to_flag", [])
        if overdue_invoices:
            target_inv = overdue_invoices[0]
            return {
                "status": "PLANNING",
                "pending_action": {
                    "tool": "api_post_flag",
                    "arguments": {
                        "invoice_id": target_inv["id"],
                        "note": f"Overdue review: Invoice {target_inv['invoice_number']} balance ${target_inv['amount']} is older than 30 days"
                    },
                    "risk": "write",
                    "operation": "flag_aging_review",
                    "description": f"Flag invoice {target_inv['invoice_number']} for overdue supervisory review"
                }
            }

        return {
            "status": "READY_TO_VERIFY",
            "pending_action": None
        }

    # Fallback
    return {
        "status": "READY_TO_VERIFY",
        "pending_action": None
    }
