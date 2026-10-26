import urllib.request
import urllib.parse
import http.cookiejar
from html.parser import HTMLParser
import json
import os
from typing import Dict, Any, List, Optional

class PageHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.in_title = False
        self.headings = []
        self.current_heading_tag = None
        self.current_heading_text = ""
        
        self.alerts = []
        self.current_alert_class = None
        self.current_alert_text = ""
        
        self.forms = []
        self.current_form = None
        
        self.tables = []
        self.current_table = None
        self.current_row = None
        self.in_th = False
        self.in_td = False
        self.cell_text = ""
        
        self.links = []
        self.current_link = None
        self.current_link_text = ""
        
        self.labels = {}  # for_id -> label text
        self.current_label_for = None
        self.current_label_text = ""

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        tag_lower = tag.lower()

        if tag_lower == "title":
            self.in_title = True
        elif tag_lower in ("h1", "h2", "h3"):
            self.current_heading_tag = tag_lower
            self.current_heading_text = ""
        elif "class" in attr_dict and any(c in attr_dict["class"] for c in ("alert", "alert-error", "alert-success", "alert-banner")):
            self.current_alert_class = attr_dict["class"]
            self.current_alert_text = ""
        elif tag_lower == "label":
            self.current_label_for = attr_dict.get("for")
            self.current_label_text = ""
        elif tag_lower == "form":
            self.current_form = {
                "id": attr_dict.get("id", f"form_{len(self.forms) + 1}"),
                "action": attr_dict.get("action", ""),
                "method": attr_dict.get("method", "POST").upper(),
                "fields": []
            }
        elif tag_lower in ("input", "select", "textarea") and self.current_form is not None:
            field_name = attr_dict.get("name")
            if field_name:
                field_id = attr_dict.get("id", "")
                self.current_form["fields"].append({
                    "id": field_id,
                    "name": field_name,
                    "type": attr_dict.get("type", "text"),
                    "value": attr_dict.get("value", ""),
                    "required": "required" in attr_dict,
                    "placeholder": attr_dict.get("placeholder", ""),
                    "label": self.labels.get(field_id, "")
                })
        elif tag_lower == "table":
            self.current_table = {
                "id": attr_dict.get("id", f"table_{len(self.tables) + 1}"),
                "headers": [],
                "rows": []
            }
        elif tag_lower == "tr" and self.current_table is not None:
            self.current_row = []
        elif tag_lower == "th" and self.current_table is not None:
            self.in_th = True
            self.cell_text = ""
        elif tag_lower == "td" and self.current_table is not None:
            self.in_td = True
            self.cell_text = ""
        elif tag_lower == "a":
            self.current_link = {
                "id": attr_dict.get("id", f"link_{len(self.links) + 1}"),
                "href": attr_dict.get("href", "")
            }
            self.current_link_text = ""

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self.in_title = False
        elif tag_lower in ("h1", "h2", "h3") and self.current_heading_tag == tag_lower:
            text = self.current_heading_text.strip()
            if text:
                self.headings.append(text)
            self.current_heading_tag = None
        elif self.current_alert_class and tag_lower in ("div", "p"):
            text = self.current_alert_text.strip()
            if text:
                self.alerts.append({"type": self.current_alert_class, "message": text})
            self.current_alert_class = None
        elif tag_lower == "label":
            if self.current_label_for and self.current_label_text:
                self.labels[self.current_label_for] = self.current_label_text.strip()
            self.current_label_for = None
        elif tag_lower == "form" and self.current_form is not None:
            # Back-fill labels if captured
            for f in self.current_form["fields"]:
                if f["id"] in self.labels:
                    f["label"] = self.labels[f["id"]]
            self.forms.append(self.current_form)
            self.current_form = None
        elif tag_lower == "th" and self.current_table is not None:
            self.in_th = False
            self.current_table["headers"].append(self.cell_text.strip())
        elif tag_lower == "td" and self.current_row is not None:
            self.in_td = False
            self.current_row.append(self.cell_text.strip())
        elif tag_lower == "tr" and self.current_table is not None:
            if self.current_row:
                # Convert to dict if headers match row count
                headers = self.current_table["headers"]
                if headers and len(headers) == len(self.current_row):
                    row_dict = dict(zip(headers, self.current_row))
                    self.current_table["rows"].append(row_dict)
                else:
                    self.current_table["rows"].append(self.current_row)
            self.current_row = None
        elif tag_lower == "table" and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None
        elif tag_lower == "a" and self.current_link is not None:
            self.current_link["text"] = self.current_link_text.strip()
            self.links.append(self.current_link)
            self.current_link = None

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.current_heading_tag:
            self.current_heading_text += data
        if self.current_alert_class:
            self.current_alert_text += " " + data.strip()
        if self.current_label_for is not None:
            self.current_label_text += " " + data.strip()
        if self.in_th or self.in_td:
            self.cell_text += " " + data.strip()
        if self.current_link is not None:
            self.current_link_text += " " + data.strip()


class WebFormSession:
    """
    Standard-library based browser session simulator.
    Interacts with server-rendered web portals with cookies, CSRF, form submission,
    and credential injection without any browser binaries.
    """
    def __init__(self, base_url: str = "http://localhost:4000", manifest_path: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.last_url = ""
        self.last_page_model = {}
        
        # Load credentials and rules from manifest
        self.manifest = {}
        if manifest_path and os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                self.manifest = json.load(f)

    def _resolve_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return f"{self.base_url}/{path_or_url.lstrip('/')}"

    def parse_page(self, html_content: str, url: str, status_code: int = 200) -> Dict[str, Any]:
        parser = PageHTMLParser()
        parser.feed(html_content)
        
        # Determine current CSRF token from cookies if available
        csrf_token = None
        for cookie in self.cookie_jar:
            if cookie.name == "centra_csrf":
                csrf_token = cookie.value
                break
                
        return {
            "url": url,
            "status_code": status_code,
            "title": parser.title.strip(),
            "alerts": parser.alerts,
            "headings": parser.headings,
            "forms": parser.forms,
            "tables": parser.tables,
            "links": parser.links,
            "csrf_token": csrf_token
        }

    def web_open(self, path: str, timeout: float = 3.0) -> Dict[str, Any]:
        url = self._resolve_url(path)
        req = urllib.request.Request(url, headers={"User-Agent": "CentraOperator/1.0 (Autonomous Company Operator)"})
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                self.last_url = resp.geturl()
                html = resp.read().decode("utf-8")
                self.last_page_model = self.parse_page(html, self.last_url, resp.status)
                return self.last_page_model
        except urllib.error.HTTPError as e:
            html = e.read().decode("utf-8")
            self.last_url = e.geturl()
            self.last_page_model = self.parse_page(html, self.last_url, e.code)
            return self.last_page_model
        except Exception as e:
            self.last_page_model = {"url": url, "error": str(e), "forms": [], "tables": [], "alerts": [{"type": "alert-error", "message": str(e)}], "links": []}
            return self.last_page_model

    def web_follow(self, link_id_or_text: str) -> Dict[str, Any]:
        if not self.last_page_model or "links" not in self.last_page_model:
            raise ValueError("No active page loaded. Call web_open first.")
        
        target_link = None
        for link in self.last_page_model["links"]:
            if link["id"] == link_id_or_text or link["text"].lower() == link_id_or_text.lower():
                target_link = link
                break
                
        if not target_link:
            raise ValueError(f"Link '{link_id_or_text}' not found on page {self.last_url}")
            
        return self.web_open(target_link["href"])

    def web_submit(self, form_id: str, fields: Dict[str, Any], credential_ref: Optional[str] = None, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Submits form. If credential_ref is provided, injects secrets from manifest
        without exposing credentials to the LLM.
        """
        if not self.last_page_model or "forms" not in self.last_page_model:
            raise ValueError("No active page loaded. Call web_open first.")
            
        target_form = None
        for form in self.last_page_model["forms"]:
            if form["id"] == form_id:
                target_form = form
                break
                
        if not target_form:
            # Fallback to first form if only one exists
            if len(self.last_page_model["forms"]) == 1:
                target_form = self.last_page_model["forms"][0]
            else:
                raise ValueError(f"Form '{form_id}' not found on page {self.last_url}")

        payload = {}
        # Prepopulate default values and hidden fields (like CSRF tokens)
        for field in target_form["fields"]:
            if field["value"]:
                payload[field["name"]] = field["value"]

        # Merge provided fields
        payload.update(fields)

        # Secure Credential Injection (Least-Privilege Boundary)
        if credential_ref:
            creds_config = self.manifest.get("credentials", {}).get(credential_ref)
            if creds_config:
                payload[creds_config["username_field"]] = creds_config["username_val"]
                payload[creds_config["password_field"]] = creds_config["password_val"]
            else:
                raise ValueError(f"Credential reference '{credential_ref}' not found in manifest")

        # Encode and POST
        encoded_data = urllib.parse.urlencode(payload).encode("utf-8")
        action_url = self._resolve_url(target_form["action"] or self.last_url)
        req = urllib.request.Request(
            action_url,
            data=encoded_data,
            headers={
                "User-Agent": "CentraOperator/1.0",
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )

        try:
            with self.opener.open(req, timeout=timeout) as resp:
                self.last_url = resp.geturl()
                html = resp.read().decode("utf-8")
                self.last_page_model = self.parse_page(html, self.last_url, resp.status)
                return self.last_page_model
        except urllib.error.HTTPError as e:
            html = e.read().decode("utf-8")
            self.last_url = e.geturl()
            self.last_page_model = self.parse_page(html, self.last_url, e.code)
            return self.last_page_model
        except Exception as e:
            self.last_page_model = {"url": action_url, "error": str(e), "forms": [], "tables": [], "alerts": [{"type": "alert-error", "message": str(e)}], "links": []}
            return self.last_page_model
