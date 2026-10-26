import json
import os
from typing import Dict, Any, List, Optional

try:
    from tools.web import WebFormSession
    from tools.erp_api import ErpApiClient
    from tools.inbox import InboxTool
except (ImportError, ValueError):
    from .web import WebFormSession
    from .erp_api import ErpApiClient
    from .inbox import InboxTool

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "inbox_list",
            "description": "Lists all documents and emails in the company inbox.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "inbox_read",
            "description": "Reads the plain-text content of a specific document or invoice from the inbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "The name of the file to read (e.g. acme_inv_2041.txt)"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_open",
            "description": "Opens a web page in CentraERP and returns a compact structured page model (forms, tables, alerts, links).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "URL path to open, e.g. '/login', '/dashboard', '/invoices/new', '/po'"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_follow",
            "description": "Follows a hyperlink on the currently open page by its link ID or anchor text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "link_id": {"type": "string", "description": "The ID or exact text of the link to follow"}
                },
                "required": ["link_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_submit",
            "description": "Submits a web form on the currently open page. If credential_ref is specified, credentials are injected by the tool layer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "form_id": {"type": "string", "description": "The ID of the form to submit"},
                    "fields": {"type": "object", "description": "Key-value pairs of form inputs"},
                    "credential_ref": {"type": "string", "description": "Optional name of credential secret to inject (e.g. 'erp_ap_clerk')"}
                },
                "required": ["form_id", "fields"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "api_get",
            "description": "Queries CentraERP's read-only JSON API using an independent read-only audit token. Used for verification and PO inspection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "API path, e.g. '/api/invoices' or '/api/po'"},
                    "query": {"type": "object", "description": "Optional query parameters filter"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "api_post_flag",
            "description": "Flags an overdue invoice for managerial review in CentraERP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string", "description": "The ID or invoice number of the target invoice"},
                    "note": {"type": "string", "description": "Reason or aging period note"}
                },
                "required": ["invoice_id", "note"]
            }
        }
    }
]

class ToolRegistry:
    def __init__(self, erp_base_url: str = "http://localhost:4000", manifest_path: Optional[str] = None):
        if manifest_path is None:
            manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "manifest.json")
        self.web = WebFormSession(base_url=erp_base_url, manifest_path=manifest_path)
        self.api = ErpApiClient(base_url=erp_base_url)
        self.inbox = InboxTool()
        self.manifest_path = manifest_path

    def get_definitions(self) -> List[Dict[str, Any]]:
        return TOOL_DEFINITIONS

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if tool_name == "inbox_list":
            return self.inbox.list_inbox()
        elif tool_name == "inbox_read":
            return self.inbox.read_document(arguments.get("filename"))
        elif tool_name == "web_open":
            return self.web.web_open(arguments.get("path"))
        elif tool_name == "web_follow":
            return self.web.web_follow(arguments.get("link_id"))
        elif tool_name == "web_submit":
            return self.web.web_submit(
                form_id=arguments.get("form_id"),
                fields=arguments.get("fields", {}),
                credential_ref=arguments.get("credential_ref")
            )
        elif tool_name == "api_get":
            return self.api.api_get(
                path=arguments.get("path"),
                query=arguments.get("query")
            )
        elif tool_name == "api_post_flag":
            return self.api.api_post_flag(
                invoice_id=arguments.get("invoice_id"),
                note=arguments.get("note", "")
            )
        else:
            raise ValueError(f"Unknown tool: '{tool_name}'")
