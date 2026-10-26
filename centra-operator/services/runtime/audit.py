import hashlib
import json
import time
from typing import List, Dict, Any, Optional

def canonical_json(obj: Any) -> str:
    """Produces deterministic canonical JSON serialization for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(',', ':'))

class AuditLogger:
    """
    Tamper-evident audit log with SHA-256 hash chaining.
    Every action, observation, gate decision, and verification check
    is permanently recorded in a cryptographically linked chain.
    """
    GENESIS_HASH = "0" * 64

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.chain: List[Dict[str, Any]] = []

    def append_event(self, event_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        prev_hash = self.chain[-1]["hash"] if self.chain else self.GENESIS_HASH
        timestamp = time.time()
        
        entry_body = {
            "task_id": self.task_id,
            "seq": len(self.chain),
            "timestamp": timestamp,
            "event_type": event_type,
            "details": details
        }
        
        payload_to_hash = f"{prev_hash}{canonical_json(entry_body)}"
        entry_hash = hashlib.sha256(payload_to_hash.encode("utf-8")).hexdigest()
        
        record = {
            **entry_body,
            "prev_hash": prev_hash,
            "hash": entry_hash
        }
        self.chain.append(record)
        return record

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """
        Verifies that no entry in the chain has been modified or tampered with.
        """
        expected_prev = self.GENESIS_HASH
        for idx, entry in enumerate(self.chain):
            if entry["prev_hash"] != expected_prev:
                return {
                    "valid": False,
                    "tampered_at_index": idx,
                    "reason": f"Previous hash mismatch at sequence {idx}"
                }
            
            entry_body = {
                "task_id": entry["task_id"],
                "seq": entry["seq"],
                "timestamp": entry["timestamp"],
                "event_type": entry["event_type"],
                "details": entry["details"]
            }
            computed_hash = hashlib.sha256(f"{expected_prev}{canonical_json(entry_body)}".encode("utf-8")).hexdigest()
            if computed_hash != entry["hash"]:
                return {
                    "valid": False,
                    "tampered_at_index": idx,
                    "reason": f"Content tampering detected at sequence {idx}: hash recalculation mismatch"
                }
            expected_prev = entry["hash"]

        return {
            "valid": True,
            "entries_count": len(self.chain),
            "final_hash": self.chain[-1]["hash"] if self.chain else self.GENESIS_HASH
        }
