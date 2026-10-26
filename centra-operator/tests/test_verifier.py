import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.runtime.graph.nodes.verify import verify_node
from services.runtime.tools.erp_api import ErpApiClient
from services.runtime.audit import AuditLogger

class MockErpApiClient:
    def __init__(self, return_invoices=None):
        self.return_invoices = return_invoices if return_invoices is not None else []

    def api_get(self, path, query=None):
        return {"count": len(self.return_invoices), "invoices": self.return_invoices}

class TestIndependentVerification(unittest.TestCase):
    def test_missing_db_record_fails_verification(self):
        # UI said "Success", but ERP DB has 0 records (lying_success fault)
        state = {
            "task_id": "t_lying",
            "facts": {
                "intent": "invoice_processing",
                "invoice_number": "INV-MOCK-999",
                "amount": 1200.00,
                "vendor": "Acme Corporation"
            },
            "criteria": [],
            "history": []
        }
        mock_api = MockErpApiClient(return_invoices=[])
        audit = AuditLogger(task_id="t_lying")

        result = verify_node(state, mock_api, audit)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["verification"]["verified"])
        self.assertIn("not found in General Ledger", result["verification"]["failure_reasons"][0])

    def test_amount_mismatch_fails_verification(self):
        # DB record exists, but amount does not match source invoice
        state = {
            "task_id": "t_mismatch",
            "facts": {
                "intent": "invoice_processing",
                "invoice_number": "INV-2041",
                "amount": 1200.00,
                "vendor": "Acme Corporation"
            },
            "criteria": [],
            "history": []
        }
        mock_api = MockErpApiClient(return_invoices=[{
            "invoice_number": "INV-2041",
            "amount": 1500.00, # Corrupted or altered amount
            "status": "POSTED"
        }])
        audit = AuditLogger(task_id="t_mismatch")

        result = verify_node(state, mock_api, audit)
        self.assertEqual(result["status"], "VERIFICATION_FAILED")
        self.assertFalse(result["verification"]["verified"])
        self.assertIn("Amount mismatch", result["verification"]["failure_reasons"][0])

    def test_valid_db_record_passes_verification(self):
        state = {
            "task_id": "t_valid",
            "facts": {
                "intent": "invoice_processing",
                "invoice_number": "INV-2041",
                "amount": 1200.00,
                "vendor": "Acme Corporation"
            },
            "criteria": [],
            "history": []
        }
        mock_api = MockErpApiClient(return_invoices=[{
            "invoice_number": "INV-2041",
            "amount": 1200.00,
            "status": "POSTED",
            "created_at": "2026-10-26T12:00:00Z"
        }])
        audit = AuditLogger(task_id="t_valid")

        result = verify_node(state, mock_api, audit)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(result["verification"]["verified"])
        self.assertEqual(len(result["evidence"]), 1)

if __name__ == "__main__":
    unittest.main()
