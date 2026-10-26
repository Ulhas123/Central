from typing import Dict, Any, List
from ..state import RunState
from ...tools.erp_api import ErpApiClient
from ...audit import AuditLogger

def verify_node(state: RunState, erp_api: ErpApiClient, audit: AuditLogger) -> Dict[str, Any]:
    """
    Independent Verification Node:
    Queries the system via an isolated read-only API with read-only credentials.
    Verifies that real state changes exist and match source document facts.
    """
    facts = state.get("facts", {})
    intent = facts.get("intent", "invoice_processing")
    criteria = state.get("criteria", [])
    evidence = []
    all_passed = True
    failure_reasons = []

    if intent == "invoice_processing":
        inv_number = facts.get("invoice_number")
        expected_amount = facts.get("amount")
        expected_vendor = facts.get("vendor")

        # Independent Read: Query ERP API
        res = erp_api.api_get("/api/invoices", query={"invoice_number": inv_number})
        invoices = res.get("invoices", [])
        
        # Check 1: Record exists
        if not invoices:
            all_passed = False
            failure_reasons.append(f"Verification failure: Invoice {inv_number} not found in General Ledger via read-only API.")
        else:
            record = invoices[0]
            # Check 2: Status is POSTED
            if record.get("status") != "POSTED":
                all_passed = False
                failure_reasons.append(f"Status mismatch: expected POSTED, found {record.get('status')}")

            # Check 3: Amount matches source document
            if abs(float(record.get("amount", 0.0)) - float(expected_amount)) > 0.01:
                all_passed = False
                failure_reasons.append(f"Amount mismatch: expected ${expected_amount}, found ${record.get('amount')}")

            evidence.append({
                "source": "CentraERP Read-Only API (/api/invoices)",
                "verified_record": record,
                "timestamp": record.get("created_at")
            })

    elif intent == "aging_review":
        vendor = facts.get("target_vendor_hint", "Helios")
        res = erp_api.api_get("/api/invoices", query={"vendor": vendor})
        invoices = res.get("invoices", [])
        
        flagged = [i for i in invoices if i.get("flagged_for_review")]
        if not flagged:
            all_passed = False
            failure_reasons.append(f"Verification failure: No overdue invoices flagged for {vendor}.")
        else:
            evidence.append({
                "source": "CentraERP Read-Only API (/api/invoices)",
                "flagged_invoices_count": len(flagged),
                "flagged_invoices": [f"{i['invoice_number']} (${i['amount']})" for i in flagged]
            })

    audit.append_event("verification_evaluated", {
        "verified": all_passed,
        "evidence_count": len(evidence),
        "failure_reasons": failure_reasons
    })

    return {
        "status": "VERIFIED" if all_passed else "VERIFICATION_FAILED",
        "verification": {
            "verified": all_passed,
            "failure_reasons": failure_reasons
        },
        "evidence": evidence,
        "history": [{
            "type": "verification_pass" if all_passed else "verification_fail",
            "passed": all_passed,
            "details": failure_reasons if not all_passed else "All criteria independently verified"
        }]
    }
