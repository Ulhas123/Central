import time
import uuid
from typing import Dict, Any, Optional

try:
    from graph.state import RunState
    from graph.nodes.understand import understand_node
    from graph.nodes.recall import recall_node
    from graph.nodes.plan import plan_node
    from graph.nodes.gate import gate_node
    from graph.nodes.act import act_node
    from graph.nodes.observe import observe_node
    from graph.nodes.adapt import adapt_node
    from graph.nodes.verify import verify_node
    from graph.nodes.complete import complete_node

    from tools.registry import ToolRegistry
    from memory.sops import SopMemoryStore
    from memory.episodic import EpisodicMemoryStore
    from audit import AuditLogger
except (ImportError, ValueError):
    from .state import RunState
    from .nodes.understand import understand_node
    from .nodes.recall import recall_node
    from .nodes.plan import plan_node
    from .nodes.gate import gate_node
    from .nodes.act import act_node
    from .nodes.observe import observe_node
    from .nodes.adapt import adapt_node
    from .nodes.verify import verify_node
    from .nodes.complete import complete_node

    from ..tools.registry import ToolRegistry
    from ..memory.sops import SopMemoryStore
    from ..memory.episodic import EpisodicMemoryStore
    from ..audit import AuditLogger

# In-Memory / Durable checkpoint storage for paused tasks awaiting human approval
CHECKPOINTS: Dict[str, Dict[str, Any]] = {}

def apply_state_update(state: RunState, updates: Dict[str, Any]):
    for k, v in updates.items():
        if k == "history" and isinstance(v, list):
            state["history"].extend(v)
        else:
            state[k] = v

class CentraWorkflowRunner:
    """
    Executes the CentraOperator state graph:
    Goal -> Understand -> Recall -> Plan -> Gate -> Act -> Observe -> Adapt -> Verify -> Complete
    """
    def __init__(self, erp_base_url: str = "http://localhost:4000", sop_dir: Optional[str] = None):
        self.registry = ToolRegistry(erp_base_url=erp_base_url)
        self.sop_store = SopMemoryStore(sops_dir=sop_dir)
        self.episodic_store = EpisodicMemoryStore()

    def create_initial_state(self, goal: str, task_id: Optional[str] = None, company_id: str = "COMP-001") -> RunState:
        tid = task_id or f"task_{uuid.uuid4().hex[:8]}"
        return {
            "task_id": tid,
            "company_id": company_id,
            "goal": goal,
            "criteria": [],
            "facts": {},
            "policies": [],
            "memories": [],
            "plan": [],
            "pending_action": None,
            "last_observation": None,
            "history": [],
            "attempts": {},
            "budget": {"max_retries": 3, "max_steps": 25},
            "verification": None,
            "status": "STARTING",
            "evidence": [],
            "interrupt_data": None
        }

    def execute_turn(self, state: RunState, audit: AuditLogger) -> RunState:
        """
        Runs the cyclic graph until either completion, terminal failure,
        or an interrupt awaiting human-in-the-loop approval.
        """
        step_count = 0
        max_steps = state.get("budget", {}).get("max_steps", 25)

        # 1. Start -> Understand & Recall
        if state["status"] in ("STARTING",):
            res_u = understand_node(state)
            apply_state_update(state, res_u)
            audit.append_event("graph_node_transition", {"from": "STARTING", "to": "UNDERSTOOD"})

            res_r = recall_node(state, self.sop_store, self.episodic_store)
            apply_state_update(state, res_r)
            audit.append_event("graph_node_transition", {"from": "UNDERSTOOD", "to": "RECALLED"})
            state["status"] = "PLANNING"

        while step_count < max_steps:
            step_count += 1
            current_status = state["status"]

            # Terminal states
            if current_status in ("COMPLETED", "FAILED", "REJECTED", "DUPLICATE_HALTED"):
                break

            # ---------------- Branch: PLANNING ----------------
            if current_status in ("PLANNING", "ADAPTING"):
                res_plan = plan_node(state)
                apply_state_update(state, res_plan)

                if state["pending_action"] is None:
                    # All steps executed -> route to verification
                    state["status"] = "VERIFYING"
                    audit.append_event("graph_node_transition", {"from": current_status, "to": "VERIFYING"})
                else:
                    # Action selected -> route to Gate
                    state["status"] = "GATING"
                    audit.append_event("graph_node_transition", {"from": current_status, "to": "GATING"})

            # ---------------- Branch: GATING ----------------
            elif current_status in ("GATING", "AWAITING_APPROVAL"):
                res_gate = gate_node(state, self.episodic_store)
                apply_state_update(state, res_gate)

                if state["status"] == "AWAITING_APPROVAL":
                    # Graph paused at HITL boundary! Checkpoint and yield
                    CHECKPOINTS[state["task_id"]] = {
                        "state": state,
                        "audit": audit,
                        "paused_at": time.time()
                    }
                    audit.append_event("graph_interrupt_yielded", {
                        "task_id": state["task_id"],
                        "reason": state.get("interrupt_data", {}).get("reason")
                    })
                    return state

                elif state["status"] == "REJECTED":
                    audit.append_event("graph_node_transition", {"from": "GATING", "to": "REJECTED"})
                    break

                elif state["status"] == "APPROVED_TO_ACT":
                    state["status"] = "ACTING"
                    audit.append_event("graph_node_transition", {"from": "GATING", "to": "ACTING"})

            # ---------------- Branch: ACTING ----------------
            elif current_status == "ACTING":
                res_act = act_node(state, self.registry, audit)
                apply_state_update(state, res_act)

                if state["status"] == "DUPLICATE_LOCKED":
                    break

                # Route to Observe
                state["status"] = "OBSERVING"
                audit.append_event("graph_node_transition", {"from": "ACTING", "to": "OBSERVING"})

            # ---------------- Branch: OBSERVING ----------------
            elif current_status == "OBSERVING":
                res_obs = observe_node(state)
                apply_state_update(state, res_obs)

                anomalies = state.get("last_observation", {}).get("anomalies", [])
                if anomalies:
                    # Environmental fault or anomaly detected -> route to Adapt
                    state["status"] = "ADAPTING"
                    audit.append_event("graph_node_transition", {"from": "OBSERVING", "to": "ADAPTING"})
                    res_adapt = adapt_node(state)
                    apply_state_update(state, res_adapt)
                    
                    if state.get("pending_action"):
                        state["status"] = "GATING"
                    elif state["status"] == "ADAPTING":
                        state["status"] = "PLANNING"
                else:
                    # Clean observation -> route back to Plan
                    state["status"] = "PLANNING"
                    audit.append_event("graph_node_transition", {"from": "OBSERVING", "to": "PLANNING"})

            # ---------------- Branch: VERIFYING ----------------
            elif current_status == "VERIFYING":
                res_verify = verify_node(state, self.registry.api, audit)
                apply_state_update(state, res_verify)

                if state["verification"] and state["verification"].get("verified"):
                    state["status"] = "COMPLETING"
                    audit.append_event("graph_node_transition", {"from": "VERIFYING", "to": "COMPLETING"})
                    res_complete = complete_node(state, audit)
                    apply_state_update(state, res_complete)
                    break
                else:
                    # Verification failed -> route to Adapt
                    state["status"] = "ADAPTING"
                    audit.append_event("graph_node_transition", {"from": "VERIFYING", "to": "ADAPTING"})
                    res_adapt = adapt_node(state)
                    apply_state_update(state, res_adapt)
                    if state["status"] in ("FAILED", "DUPLICATE_HALTED"):
                        break
                    elif state.get("pending_action"):
                        state["status"] = "GATING"

        return state

    def resume_task(self, task_id: str, human_decision: Dict[str, Any]) -> RunState:
        """
        Resumes a paused graph checkpoint using human decision (approval/rejection/note).
        """
        if task_id not in CHECKPOINTS:
            raise KeyError(f"No paused checkpoint found for task '{task_id}'")

        ckpt = CHECKPOINTS[task_id]
        state: RunState = ckpt["state"]
        audit: AuditLogger = ckpt["audit"]

        # Inject decision into state
        state["facts"]["human_decision"] = human_decision
        audit.append_event("human_decision_resumed", human_decision)

        # Resume execution
        del CHECKPOINTS[task_id]
        return self.execute_turn(state, audit)
