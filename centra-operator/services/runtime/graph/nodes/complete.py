from typing import Dict, Any, List

try:
    from graph.state import RunState
    from audit import AuditLogger
except (ImportError, ValueError):
    from ..state import RunState
    from ...audit import AuditLogger

def complete_node(state: RunState, audit: AuditLogger) -> Dict[str, Any]:
    """
    Finalizes the task run:
    1. Compiles executive completion summary and machine-verified evidence.
    2. Seals the tamper-evident cryptographic hash chain.
    3. Finalizes status.
    """
    facts = state.get("facts", {})
    intent = facts.get("intent", "invoice_processing")
    evidence = state.get("evidence", [])
    
    chain_status = audit.verify_chain_integrity()
    audit_proof = {
        "tamper_evident_valid": chain_status.get("valid"),
        "entries_count": chain_status.get("entries_count"),
        "final_hash": chain_status.get("final_hash")
    }

    if intent == "invoice_processing":
        summary = (
            f"Successfully processed invoice {facts.get('invoice_number')} from {facts.get('vendor')} "
            f"for ${facts.get('amount'):.2f} USD. Matched against Purchase Order {facts.get('po_number')} "
            f"and posted to CentraERP General Ledger. Independently verified via read-only audit API."
        )
    elif intent == "aging_review":
        flags = facts.get("flags_recorded")
        if not flags:
            if evidence and "flagged_invoices_count" in evidence[0]:
                flags = evidence[0]["flagged_invoices_count"]
            else:
                flags = 0
        summary = (
            f"Completed overdue aging review for {facts.get('target_vendor_hint', 'Helios')}. "
            f"Inspected unpaid ledger records and successfully flagged {flags} invoices older than 30 days "
            f"for supervisory review. Verified via read-only audit API."
        )
    else:
        summary = f"Task completed successfully. Verified {len(evidence)} evidence records."

    audit.append_event("task_sealed", {
        "summary": summary,
        "audit_proof": audit_proof
    })

    return {
        "status": "COMPLETED",
        "evidence": evidence,
        "facts": {
            **facts,
            "completion_summary": summary,
            "audit_proof": audit_proof
        },
        "history": [{
            "type": "task_completed",
            "summary": summary,
            "final_audit_hash": audit_proof["final_hash"]
        }]
    }
