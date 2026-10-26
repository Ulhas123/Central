import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.runtime.tools.web import PageHTMLParser, WebFormSession

class TestWebFormTool(unittest.TestCase):
    def test_page_model_extraction(self):
        sample_html = """
        <!DOCTYPE html>
        <html>
        <head><title>CentraERP Invoices</title></head>
        <body>
          <div class="alert-error">Session expired, please re-login</div>
          <h2>Invoices Ledger</h2>
          <table id="table-invoices">
            <thead>
              <tr><th>Invoice #</th><th>Vendor</th><th>Amount</th></tr>
            </thead>
            <tbody>
              <tr><td>INV-100</td><td>Acme Corp</td><td>$1,200.00</td></tr>
            </tbody>
          </table>
          <form id="form-invoice-entry" action="/invoices" method="POST">
            <input type="hidden" name="csrf_token" value="abc123token" />
            <label for="vendor">Vendor Name</label>
            <input type="text" id="vendor" name="vendor" value="" required />
            <button type="submit">Submit</button>
          </form>
          <a id="link-dashboard" href="/dashboard">Dashboard</a>
        </body>
        </html>
        """
        parser = PageHTMLParser()
        parser.feed(sample_html)

        self.assertEqual(parser.title, "CentraERP Invoices")
        self.assertEqual(len(parser.alerts), 1)
        self.assertEqual(parser.alerts[0]["message"], "Session expired, please re-login")
        self.assertEqual(len(parser.tables), 1)
        self.assertEqual(parser.tables[0]["headers"], ["Invoice #", "Vendor", "Amount"])
        self.assertEqual(len(parser.tables[0]["rows"]), 1)
        self.assertEqual(parser.tables[0]["rows"][0]["Invoice #"], "INV-100")
        
        self.assertEqual(len(parser.forms), 1)
        self.assertEqual(parser.forms[0]["id"], "form-invoice-entry")
        fields = parser.forms[0]["fields"]
        self.assertTrue(any(f["name"] == "csrf_token" and f["value"] == "abc123token" for f in fields))
        self.assertTrue(any(f["name"] == "vendor" and f["required"] for f in fields))
        
        self.assertEqual(len(parser.links), 1)
        self.assertEqual(parser.links[0]["id"], "link-dashboard")
        self.assertEqual(parser.links[0]["href"], "/dashboard")

if __name__ == "__main__":
    unittest.main()
