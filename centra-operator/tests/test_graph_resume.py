import os
import sys
import unittest
import urllib.request
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.runtime.graph.workflow import CentraWorkflowRunner, CHECKPOINTS
from services.runtime.audit import AuditLogger
from services.runtime.graph.nodes.act import IDEMPOTENCY_STORE

class TestGraphPauseAndResume(unittest.TestCase):
    def setUp(self):
        IDEMPOTENCY_STORE.clear()
        CHECKPOINTS.clear()
        try:
            req = urllib.request.Request("http://localhost:4000/__reset", data=b"{}", headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                pass
        except Exception:
            pass

    def test_over_limit_triggers_interrupt_and_resumes_cleanly(self):
        runner = CentraWorkflowRunner(erp_base_url="http://localhost:4000")
        audit = AuditLogger(task_id="task_test_resume")
        state = runner.create_initial_state(
            goal="Process the Apex Global invoice for security appliance",
            task_id="task_test_resume"
        )

        # 1. First execution turn - should pause at Gate due to $14,500 > $5,000 threshold
        paused_state = runner.execute_turn(state, audit)
        self.assertEqual(paused_state["status"], "AWAITING_APPROVAL")
        self.assertIsNotNone(paused_state["interrupt_data"])
        self.assertIn("exceeds standard automatic processing threshold", paused_state["interrupt_data"]["reason"])
        self.assertIn("task_test_resume", CHECKPOINTS)

        # 2. Simulate human supervisor approving the transaction
        decision = {
            "approved": True,
            "note": "Special director approval granted for infrastructure upgrade",
            "approver": "Director of Finance"
        }
        resumed_state = runner.resume_task("task_test_resume", decision)
        
        # Checkpoint should be consumed
        self.assertNotIn("task_test_resume", CHECKPOINTS)
        self.assertIn("human_approval_received", [h["type"] for h in resumed_state["history"]])

if __name__ == "__main__":
    unittest.main()
