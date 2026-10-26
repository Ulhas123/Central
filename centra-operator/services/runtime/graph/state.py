from typing import TypedDict, List, Dict, Any, Optional, Annotated
import operator

class RunState(TypedDict):
    task_id: str
    company_id: str
    goal: str
    criteria: List[Dict[str, Any]]             # acceptance checks, derived in `understand`
    facts: Dict[str, Any]                      # anything learned: extracted fields, IDs, page data
    policies: List[Dict[str, Any]]             # SOPs retrieved from Qdrant (with structured payloads)
    memories: List[Dict[str, Any]]             # past human decisions retrieved from Qdrant
    plan: List[Dict[str, Any]]                 # revisable list of intended steps
    pending_action: Optional[Dict[str, Any]]
    last_observation: Optional[Dict[str, Any]]
    history: Annotated[List[Dict[str, Any]], operator.add]   # every action + observation
    attempts: Dict[str, int]                   # per-step retry counts
    budget: Dict[str, int]                     # max steps, max retries, max LLM calls
    verification: Optional[Dict[str, Any]]
    status: str                                # "STARTING", "PLANNING", "AWAITING_APPROVAL", "ACTING", "OBSERVING", "ADAPTING", "VERIFYING", "COMPLETED", "FAILED", "REJECTED"
    evidence: List[Dict[str, Any]]
    interrupt_data: Optional[Dict[str, Any]]   # Details provided when waiting for human approval
