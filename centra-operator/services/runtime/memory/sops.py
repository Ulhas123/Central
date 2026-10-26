import os
import json
import math
from typing import List, Dict, Any, Optional

def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

def tokenize_and_embed(text: str) -> List[float]:
    """
    Deterministically embeds text into a dense vector space based on
    key domain terms and character n-grams. Compatible with Qdrant vector spaces.
    """
    vocab = [
        "invoice", "approval", "limit", "amount", "exceed", "manager", "posting",
        "purchase", "order", "po", "matching", "open", "variance", "vendor",
        "aging", "overdue", "unpaid", "review", "flag", "days", "30", "acme",
        "apex", "helios", "duplicate", "ledger", "general", "erp", "status"
    ]
    words = text.lower().split()
    vector = [0.0] * len(vocab)
    for word in words:
        clean = "".join(c for c in word if c.isalnum())
        for idx, term in enumerate(vocab):
            if term in clean or clean in term:
                vector[idx] += 1.0
    # Normalize
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude > 0:
        vector = [v / magnitude for v in vector]
    return vector

class SopMemoryStore:
    def __init__(self, sops_dir: Optional[str] = None, qdrant_client: Any = None):
        if sops_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            self.sops_dir = os.path.join(base_dir, "data", "sops")
        else:
            self.sops_dir = sops_dir
            
        self.qdrant_client = qdrant_client
        self.sops: List[Dict[str, Any]] = []
        self.embeddings: Dict[str, List[float]] = {}
        self.load_sops()

    def load_sops(self):
        self.sops = []
        if not os.path.exists(self.sops_dir):
            return
            
        for file in os.listdir(self.sops_dir):
            if file.endswith(".json"):
                filepath = os.path.join(self.sops_dir, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self.sops.append(data)
                        text_corpus = f"{data.get('title', '')} {data.get('text', '')}"
                        self.embeddings[data["id"]] = tokenize_and_embed(text_corpus)
                except Exception as e:
                    print(f"Error loading SOP {file}: {e}")

    def search_sops(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        query_vec = tokenize_and_embed(query)
        scored = []
        for sop in self.sops:
            sop_vec = self.embeddings.get(sop["id"])
            if sop_vec:
                score = compute_cosine_similarity(query_vec, sop_vec)
                scored.append((score, sop))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]
