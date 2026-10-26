import re
from typing import Dict, Any, List
from ..state import RunState

def extract_invoice_fields_from_text(text: str) -> Dict[str, Any]:
    facts = {}
    
    vendor_m = re.search(r'Vendor:\s*(.+)', text, re.IGNORECASE)
    if vendor_m: facts["vendor"] = vendor_m.group(1).strip()
    
    inv_m = re.search(r'Invoice Number:\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
    if inv_m: facts["invoice_number"] = inv_m.group(1).strip()
    
    amount_m = re.search(r'Total Amount:\s*\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
    if amount_m:
        raw_val = amount_m.group(1).replace(',', '')
        try:
            facts["amount"] = float(raw_val)
        except ValueError:
            pass

    po_m = re.search(r'Purchase Order Number:\s*([A-Za-z0-9\-]+)', text, re.IGNORECASE)
    if po_m: facts["po_number"] = po_m.group(1).strip()
    
    due_m = re.search(r'Due Date:\s*([0-9\-]+)', text, re.IGNORECASE)
    if due_m: facts["due_date"] = due_m.group(1).strip()

    return facts

def observe_node(state: RunState) -> Dict[str, Any]:
    """
    Observer: reduces tool outputs to facts and flags environmental anomalies or faults.
    """
    last_obs = state.get("last_observation", {})
    tool = last_obs.get("tool")
    output = last_obs.get("output")
    facts = dict(state.get("facts", {}))
    anomalies = []
    
    # 1. Processing inbox_read output
    if tool == "inbox_read" and isinstance(output, dict):
        raw_content = output.get("content", "")
        facts["raw_document"] = raw_content
        extracted = extract_invoice_fields_from_text(raw_content)
        facts.update(extracted)

    # 2. Processing api_get output
    elif tool == "api_get" and isinstance(output, dict):
        if "pos" in output and output["pos"]:
            facts["po_record"] = output["pos"][0]
            facts["po_status"] = output["pos"][0].get("status")
            facts["po_variance"] = abs(facts.get("amount", 0.0) - output["pos"][0].get("amount", 0.0))
        if "invoices" in output:
            facts["unpaid_invoices"] = output["invoices"]
            # Identify overdue (>30 days) invoices for aging task
            overdue = [inv for inv in output["invoices"] if not inv.get("flagged_for_review") and inv.get("status") == "UNPAID"]
            facts["overdue_to_flag"] = overdue

    # 3. Processing web_open or web_submit output
    elif tool in ("web_open", "web_submit") and isinstance(output, dict):
        facts["current_page_model"] = output
        url = output.get("url", "")
        title = output.get("title", "")
        alerts = output.get("alerts", [])

        # Check for Session Expiry Fault
        if "/login" in url or "Login" in title:
            anomalies.append({
                "type": "session_expiry",
                "message": "Session expired or authentication required; landed on login page."
            })

        # Check for Interstitial Banner Fault
        if "/interstitial" in url or "Notice Required" in title:
            anomalies.append({
                "type": "interstitial_banner",
                "message": "Interstitial notice banner blocking navigation."
            })

        # Check for form validation errors / date format fault
        for alert in alerts:
            msg = alert.get("message", "")
            if "Invalid Date Format" in msg or "YYYY-MM-DD" in msg:
                anomalies.append({
                    "type": "date_format_error",
                    "message": msg
                })
            elif "Duplicate invoice" in msg:
                anomalies.append({
                    "type": "duplicate_trap",
                    "message": msg
                })
            elif "All fields are required" in msg:
                anomalies.append({
                    "type": "validation_error",
                    "message": msg
                })
            elif any(phrase in msg.lower() for phrase in ["successfully posted", "recorded successfully", "successfully recorded"]):
                facts["invoice_posted"] = True

    # 4. Processing api_post_flag output
    elif tool == "api_post_flag" and isinstance(output, dict):
        if output.get("status") == "ok":
            # Remove flagged item from remaining list
            overdue = facts.get("overdue_to_flag", [])
            if overdue:
                facts["overdue_to_flag"] = overdue[1:]
                facts["flags_recorded"] = facts.get("flags_recorded", 0) + 1

    return {
        "status": "OBSERVED",
        "facts": facts,
        "last_observation": {
            **last_obs,
            "anomalies": anomalies
        },
        "history": [{
            "type": "observe",
            "anomalies_detected": [a["type"] for a in anomalies]
        }]
    }
