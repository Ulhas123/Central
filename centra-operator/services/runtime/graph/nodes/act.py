import hashlib
import time
from typing import Dict, Any, Optional
from ..state import RunState
from ...tools.registry import ToolRegistry
from ...audit import AuditLogger

# Local fallback idempotency store when Redis is offline
IDEMPOTENCY_STORE = {}

def acquire_idempotency_lock(key: str, task_id: str, ttl_seconds: int = 86400) -> bool:
    now = time.time()
    if key in IDEMPOTENCY_STORE:
        holder, expiry = IDEMPOTENCY_STORE[key]
        if now < expiry:
            if holder == task_id:
                return True # Re-entry allowed for the same task
            return False # Locked by another task
    IDEMPOTENCY_STORE[key] = (task_id, now + ttl_seconds)
    return True

def act_node(state: RunState, registry: ToolRegistry, audit: AuditLogger) -> Dict[str, Any]:
    """
    Executes the approved tool call with idempotency guardrails and audit logging.
    """
    action = state.get("pending_action")
    if not action:
        return {"status": "NO_ACTION"}

    tool_name = action["tool"]
    args = action.get("arguments", {})
    risk = action.get("risk", "read")
    operation = action.get("operation")

    # 1. Idempotency Lock Enforcement on Writes
    if risk in ("write", "irreversible") and operation:
        facts = state.get("facts", {})
        vendor = facts.get("vendor", "")
        inv_num = facts.get("invoice_number", "") or args.get("invoice_id", "")
        lock_material = f"{operation}:{vendor}:{inv_num}"
        lock_key = f"idemp:{hashlib.sha256(lock_material.encode('utf-8')).hexdigest()}"

        acquired = acquire_idempotency_lock(lock_key, state["task_id"])
        if not acquired:
            audit.append_event("idempotency_lock_rejected", {
                "lock_key": lock_key,
                "material": lock_material,
                "reason": "Duplicate transaction detected in flight across distributed tasks"
            })
            return {
                "status": "DUPLICATE_LOCKED",
                "last_observation": {
                    "error": True,
                    "type": "duplicate_lock_violation",
                    "message": f"Idempotency violation: Transaction '{lock_material}' already processed or in-flight."
                },
                "history": [{
                    "type": "idempotency_collision",
                    "lock_key": lock_key
                }]
            }

    # 2. Audit Trail Pre-Execution
    audit.append_event("tool_dispatch", {
        "tool": tool_name,
        "arguments": args,
        "risk": risk
    })

    # 3. Tool Execution
    try:
        result = registry.execute(tool_name, args)
        return {
            "status": "ACTED",
            "last_observation": {
                "tool": tool_name,
                "success": True,
                "output": result
            },
            "history": [{
                "type": "tool_executed",
                "tool": tool_name,
                "risk": risk
            }]
        }
    except Exception as e:
        audit.append_event("tool_error", {
            "tool": tool_name,
            "error": str(e)
        })
        return {
            "status": "ACT_ERROR",
            "last_observation": {
                "tool": tool_name,
                "success": False,
                "error": str(e)
            },
            "history": [{
                "type": "tool_failure",
                "tool": tool_name,
                "error": str(e)
            }]
        }
