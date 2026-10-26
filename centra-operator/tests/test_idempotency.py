import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.runtime.graph.nodes.act import acquire_idempotency_lock, IDEMPOTENCY_STORE

class TestIdempotencyGuardrails(unittest.TestCase):
    def setUp(self):
        IDEMPOTENCY_STORE.clear()

    def test_first_task_acquires_lock(self):
        key = "idemp:test_invoice_post_acme_inv_2041"
        acquired = acquire_idempotency_lock(key, task_id="task_100")
        self.assertTrue(acquired, "First task must successfully acquire idempotency lock")

    def test_reentrant_same_task_allowed(self):
        key = "idemp:test_invoice_post_acme_inv_2041"
        acquire_idempotency_lock(key, task_id="task_100")
        # Same task retrying ambiguous network failure
        acquired_again = acquire_idempotency_lock(key, task_id="task_100")
        self.assertTrue(acquired_again, "Same task re-entry should be permitted")

    def test_concurrent_second_task_rejected(self):
        key = "idemp:test_invoice_post_acme_inv_2041"
        acquire_idempotency_lock(key, task_id="task_100")
        # Competing parallel duplicate task attempts to acquire same key
        acquired_by_other = acquire_idempotency_lock(key, task_id="task_200")
        self.assertFalse(acquired_by_other, "Second competing task must be rejected to prevent duplicate posting")

if __name__ == "__main__":
    unittest.main()
