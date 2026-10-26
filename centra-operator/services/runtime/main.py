import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# Ensure current directory is in sys.path for direct execution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from graph.workflow import CentraWorkflowRunner, CHECKPOINTS
    from graph.nodes.act import IDEMPOTENCY_STORE
    from audit import AuditLogger
except (ImportError, ValueError):
    from .graph.workflow import CentraWorkflowRunner, CHECKPOINTS
    from .graph.nodes.act import IDEMPOTENCY_STORE
    from .audit import AuditLogger

app = FastAPI(title="CentraOperator Agent Runtime", version="1.0.0")

ERP_URL = os.environ.get("ERP_BASE_URL", "http://localhost:4000")
runner = CentraWorkflowRunner(erp_base_url=ERP_URL)

# In-memory execution store for active & completed tasks
TASK_EXECUTIONS: Dict[str, Dict[str, Any]] = {}

class RunRequest(BaseModel):
    goal: str
    company_id: Optional[str] = "COMP-001"
    task_id: Optional[str] = None

class ResumeRequest(BaseModel):
    task_id: str
    approved: bool
    note: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "ok", "service": "agent-runtime", "erp_target": ERP_URL}

@app.post("/reset")
def reset_runtime():
    CHECKPOINTS.clear()
    IDEMPOTENCY_STORE.clear()
    TASK_EXECUTIONS.clear()
    return {"status": "ok", "message": "Runtime state and idempotency locks cleared"}

@app.post("/runs")
def start_run(req: RunRequest):
    state = runner.create_initial_state(goal=req.goal, task_id=req.task_id, company_id=req.company_id)
    audit = AuditLogger(task_id=state["task_id"])
    audit.append_event("task_created", {"goal": req.goal, "company_id": req.company_id})

    final_state = runner.execute_turn(state, audit)
    TASK_EXECUTIONS[final_state["task_id"]] = {
        "state": final_state,
        "audit": audit
    }

    return {
        "task_id": final_state["task_id"],
        "status": final_state["status"],
        "summary": final_state.get("facts", {}).get("completion_summary"),
        "interrupt_data": final_state.get("interrupt_data"),
        "evidence": final_state.get("evidence", []),
        "history": final_state.get("history", [])
    }

@app.post("/resume")
def resume_run(req: ResumeRequest):
    if req.task_id not in CHECKPOINTS:
        raise HTTPException(status_code=404, detail=f"No paused checkpoint found for task {req.task_id}")

    human_decision = {
        "approved": req.approved,
        "note": req.note,
        "approver": "Dashboard User"
    }

    final_state = runner.resume_task(req.task_id, human_decision)
    if req.task_id in TASK_EXECUTIONS:
        TASK_EXECUTIONS[req.task_id]["state"] = final_state

    return {
        "task_id": final_state["task_id"],
        "status": final_state["status"],
        "summary": final_state.get("facts", {}).get("completion_summary"),
        "evidence": final_state.get("evidence", []),
        "history": final_state.get("history", [])
    }

@app.get("/tasks/{task_id}/status")
def get_task_status(task_id: str):
    if task_id not in TASK_EXECUTIONS:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        
    entry = TASK_EXECUTIONS[task_id]
    state = entry["state"]
    audit: AuditLogger = entry["audit"]
    
    return {
        "task_id": task_id,
        "status": state["status"],
        "goal": state["goal"],
        "facts": state["facts"],
        "history": state["history"],
        "evidence": state["evidence"],
        "interrupt_data": state.get("interrupt_data"),
        "audit_chain": audit.chain,
        "audit_integrity": audit.verify_chain_integrity()
    }

if __name__ == "__main__":
    port = int(os.environ.get("RUNTIME_PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
