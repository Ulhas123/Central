import urllib.request
import urllib.parse
import json
from typing import Dict, Any, Optional

class ErpApiClient:
    """
    Read-only JSON API Client for CentraERP.
    Uses an independent read-only bearer token so it cannot mutate state.
    Used exclusively for verification and read paths.
    """
    def __init__(self, base_url: str = "http://localhost:4000", token: str = "ro_audit_token_9941"):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def api_get(self, path: str, query: Optional[Dict[str, Any]] = None, timeout: float = 3.0) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            qs = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
            url = f"{url}?{qs}"

        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": "CentraOperator-Verifier/1.0"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.HTTPError as e:
            data = e.read().decode("utf-8")
            try:
                err_json = json.loads(data)
                return {"error": err_json, "status_code": e.code}
            except Exception:
                return {"error": data, "status_code": e.code}
        except Exception as e:
            return {"error": str(e), "status_code": 503}

    def api_post_flag(self, invoice_id: str, note: str, timeout: float = 3.0) -> Dict[str, Any]:
        """Allows flagging an invoice for aging review (Generalization task)."""
        url = f"{self.base_url}/api/invoices/{urllib.parse.quote(invoice_id)}/flag"
        payload = json.dumps({"note": note}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "CentraOperator-Generalization/1.0"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": str(e), "status_code": 503}
