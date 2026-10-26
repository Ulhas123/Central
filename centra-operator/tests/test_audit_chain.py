import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.runtime.audit import AuditLogger

class TestTamperEvidentAuditChain(unittest.TestCase):
    def test_clean_chain_passes_integrity(self):
        audit = AuditLogger(task_id="task_test_01")
        audit.append_event("task_created", {"prompt": "Test invoice processing"})
        audit.append_event("policy_checked", {"sop": "sop-ap-approval-limit"})
        audit.append_event("action_executed", {"tool": "web_submit", "target": "/invoices"})
        audit.append_event("verified", {"status": "POSTED"})

        result = audit.verify_chain_integrity()
        self.assertTrue(result["valid"], "Clean audit chain must pass integrity check")
        self.assertEqual(result["entries_count"], 4)

    def test_tampered_entry_fails_integrity(self):
        audit = AuditLogger(task_id="task_test_02")
        audit.append_event("step_1", {"amount": 1200.00})
        audit.append_event("step_2", {"amount": 1200.00})
        audit.append_event("step_3", {"amount": 1200.00})

        # Malicious actor tampers with step_2 payload after the fact
        audit.chain[1]["details"]["amount"] = 99999.00

        result = audit.verify_chain_integrity()
        self.assertFalse(result["valid"], "Tampered audit entry must fail integrity verification")
        self.assertEqual(result["tampered_at_index"], 1)
        self.assertIn("hash recalculation mismatch", result["reason"])

if __name__ == "__main__":
    unittest.main()
