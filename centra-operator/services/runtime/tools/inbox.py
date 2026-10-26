import os
from typing import Dict, Any, List

class InboxTool:
    """
    Reads plain-text invoices and emails from the company inbox folder.
    Plain-text documents avoid bulky third-party OCR/PDF dependencies while
    exercising full natural language extraction and parsing.
    """
    def __init__(self, inbox_dir: str = None):
        if inbox_dir is None:
            # Default to ../../../data/inbox relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            self.inbox_dir = os.path.join(base_dir, "data", "inbox")
        else:
            self.inbox_dir = inbox_dir

    def list_inbox(self) -> List[str]:
        if not os.path.exists(self.inbox_dir):
            return []
        return [f for f in os.listdir(self.inbox_dir) if f.endswith(".txt")]

    def read_document(self, filename: str) -> Dict[str, Any]:
        filepath = os.path.join(self.inbox_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Document '{filename}' not found in inbox.")
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "filename": filename,
            "content": content,
            "size_bytes": len(content)
        }
