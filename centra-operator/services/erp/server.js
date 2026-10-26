const express = require('express');
const cookieParser = require('cookie-parser');
const crypto = require('crypto');
const faults = require('./faults');

const app = express();
const PORT = process.env.ERP_PORT || 4000;
const READ_ONLY_TOKEN = process.env.ERP_READ_ONLY_TOKEN || 'ro_audit_token_9941';

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());

// In-Memory Enterprise Database
const database = {
  sessions: new Map(), // sessionId -> { username, createdAt }
  pos: [
    {
      po_number: 'ACM-892',
      vendor: 'Acme Corporation',
      amount: 1200.00,
      currency: 'USD',
      status: 'OPEN',
      line_items: ['Cloud Infrastructure Consulting - 10 hrs']
    },
    {
      po_number: 'APX-104',
      vendor: 'Apex Global Inc.',
      amount: 14500.00,
      currency: 'USD',
      status: 'OPEN',
      line_items: ['Enterprise Security Appliance & Gateway']
    },
    {
      po_number: 'HEL-001',
      vendor: 'Helios Systems',
      amount: 6050.00,
      currency: 'USD',
      status: 'OPEN',
      line_items: ['Quarterly SaaS Licenses']
    }
  ],
  invoices: [
    {
      id: 'inv_seed_1',
      vendor: 'Helios Systems',
      invoice_number: 'INV-HEL-101',
      amount: 3400.00,
      po_number: 'HEL-001',
      due_date: '2026-08-15',
      status: 'UNPAID',
      flagged_for_review: false,
      created_at: '2026-08-01T09:00:00Z'
    },
    {
      id: 'inv_seed_2',
      vendor: 'Helios Systems',
      invoice_number: 'INV-HEL-102',
      amount: 1850.00,
      po_number: 'HEL-001',
      due_date: '2026-09-01',
      status: 'UNPAID',
      flagged_for_review: false,
      created_at: '2026-08-18T10:00:00Z'
    },
    {
      id: 'inv_seed_3',
      vendor: 'Helios Systems',
      invoice_number: 'INV-HEL-108',
      amount: 800.00,
      po_number: 'HEL-001',
      due_date: '2026-10-24',
      status: 'UNPAID',
      flagged_for_review: false,
      created_at: '2026-10-10T11:00:00Z'
    }
  ]
};

// Helper: Session Checker
function checkAuth(req, res, next) {
  const sessionId = req.cookies['centra_session'];
  const activeFaults = faults.getFaults();

  if (activeFaults.session_expiry) {
    if (sessionId) {
      database.sessions.delete(sessionId);
      res.clearCookie('centra_session');
    }
    return res.redirect('/login?error=session_expired');
  }

  if (!sessionId || !database.sessions.has(sessionId)) {
    return res.redirect('/login?error=unauthorized');
  }

  req.user = database.sessions.get(sessionId);
  next();
}

// Interstitial Banner Middleware
function checkInterstitial(req, res, next) {
  const activeFaults = faults.getFaults();
  if (activeFaults.interstitial_banner && !req.cookies['dismissed_banner']) {
    return res.redirect('/interstitial?return_to=' + encodeURIComponent(req.originalUrl));
  }
  next();
}

// HTML Layout Helper
function renderPage(title, body, user = null) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>${title} - CentraERP Enterprise System</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f4f6f8; margin: 0; padding: 20px; color: #333; }
    .header { background: #1a2a3a; color: #fff; padding: 12px 20px; border-radius: 6px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
    .nav a { color: #8ec5fc; text-decoration: none; margin-right: 15px; font-weight: 500; }
    .nav a:hover { text-decoration: underline; }
    .card { background: #fff; border-radius: 8px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 20px; }
    .alert-error { background: #fee2e2; border-left: 4px solid #ef4444; padding: 12px 16px; margin-bottom: 16px; color: #991b1b; }
    .alert-success { background: #dcfce7; border-left: 4px solid #22c55e; padding: 12px 16px; margin-bottom: 16px; color: #166534; }
    .alert-banner { background: #fef3c7; border: 1px solid #f59e0b; padding: 16px; border-radius: 6px; margin-bottom: 20px; color: #92400e; }
    table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e7eb; }
    th { background: #f8fafc; font-weight: 600; }
    .badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .badge-posted { background: #dcfce7; color: #166534; }
    .badge-open { background: #e0e7ff; color: #3730a3; }
    .badge-unpaid { background: #fef3c7; color: #92400e; }
    .badge-flagged { background: #fecdd3; color: #9f1239; }
    .form-group { margin-bottom: 15px; }
    label { display: block; margin-bottom: 5px; font-weight: 600; font-size: 14px; }
    input[type="text"], input[type="password"], input[type="number"], select { width: 100%; max-width: 400px; padding: 8px 10px; border: 1px solid #cbd5e1; border-radius: 4px; box-sizing: border-box; }
    button, input[type="submit"] { background: #2563eb; color: #fff; border: none; padding: 10px 18px; border-radius: 4px; font-size: 14px; font-weight: 600; cursor: pointer; }
    button:hover, input[type="submit"]:hover { background: #1d4ed8; }
  </style>
</head>
<body>
  <div class="header">
    <div style="font-weight: 700; font-size: 18px;">CentraERP Portal [Finance & Accounts Payable]</div>
    <div class="nav">
      ${user ? `
        <span style="color: #cbd5e1; margin-right: 15px;">Logged in: <strong>${user.username}</strong></span>
        <a id="link-dashboard" href="/dashboard">Dashboard</a>
        <a id="link-invoices" href="/invoices">Invoices Ledger</a>
        <a id="link-invoices-new" href="/invoices/new">New Invoice</a>
        <a id="link-po" href="/po">PO Ledger</a>
        <a id="link-logout" href="/logout">Logout</a>
      ` : `<a id="link-login" href="/login">Login</a>`}
    </div>
  </div>
  ${body}
</body>
</html>`;
}

// ------------------- Fault Injection Endpoints -------------------
app.post('/__reset', (req, res) => {
  faults.resetFaults();
  database.invoices = database.invoices.filter(i => i.id.startsWith('inv_seed_'));
  database.sessions.clear();
  res.json({ status: 'ok', invoices_count: database.invoices.length });
});

app.get('/__faults', (req, res) => {
  res.json(faults.getFaults());
});

app.post('/__faults', (req, res) => {
  const { fault, enabled } = req.body;
  if (fault === 'reset') {
    faults.resetFaults();
    return res.json({ status: 'ok', faults: faults.getFaults() });
  }
  const ok = faults.setFault(fault, enabled);
  res.json({ status: ok ? 'ok' : 'error', faults: faults.getFaults() });
});

// ------------------- Interstitial Notice Banner -------------------
app.get('/interstitial', (req, res) => {
  const returnTo = req.query.return_to || '/dashboard';
  const body = `
    <div class="card" style="max-width: 600px; margin: 40px auto; text-align: center;">
      <div class="alert-banner">
        <h2>⚠️ System Maintenance Notice</h2>
        <p>CentraERP is undergoing scheduled database maintenance. Please confirm you have reviewed the operating policy before proceeding with write transactions.</p>
      </div>
      <form id="form-dismiss-banner" method="POST" action="/dismiss-banner">
        <input type="hidden" name="return_to" value="${returnTo}" />
        <button id="btn-dismiss-banner" type="submit">Acknowledge & Continue to System</button>
      </form>
    </div>
  `;
  res.send(renderPage('Notice Required', body));
});

app.post('/dismiss-banner', (req, res) => {
  res.cookie('dismissed_banner', '1', { maxAge: 3600000 });
  const returnTo = req.body.return_to || '/dashboard';
  res.redirect(returnTo);
});

// ------------------- Authentication Routes -------------------
app.get('/login', (req, res) => {
  const errorMsg = req.query.error === 'session_expired' ? 'Your session has expired. Please re-authenticate.' :
                   req.query.error === 'invalid_credentials' ? 'Invalid username or password.' :
                   req.query.error === 'unauthorized' ? 'Authentication required to access CentraERP.' : null;
  const csrfToken = crypto.randomBytes(16).toString('hex');
  res.cookie('centra_csrf', csrfToken);

  const body = `
    <div class="card" style="max-width: 450px; margin: 50px auto;">
      <h2>ERP Authentication</h2>
      ${errorMsg ? `<div class="alert-error" id="auth-error-banner">${errorMsg}</div>` : ''}
      <form id="form-login" method="POST" action="/login">
        <input type="hidden" name="csrf_token" value="${csrfToken}" />
        <div class="form-group">
          <label for="username">Username</label>
          <input type="text" id="username" name="username" value="" required placeholder="Enter ERP username" />
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <input type="password" id="password" name="password" required placeholder="Enter password" />
        </div>
        <button id="btn-login-submit" type="submit">Sign In</button>
      </form>
    </div>
  `;
  res.send(renderPage('Login', body));
});

app.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (username === 'erp_ap_clerk' && password === 'password123') {
    const sessionId = crypto.randomBytes(24).toString('hex');
    database.sessions.set(sessionId, { username, createdAt: Date.now() });
    res.cookie('centra_session', sessionId, { httpOnly: true });
    // Reset session_expiry fault once re-authenticated
    faults.setFault('session_expiry', false);
    return res.redirect('/dashboard');
  }
  return res.redirect('/login?error=invalid_credentials');
});

app.get('/logout', (req, res) => {
  const sessionId = req.cookies['centra_session'];
  if (sessionId) database.sessions.delete(sessionId);
  res.clearCookie('centra_session');
  res.redirect('/login');
});

// ------------------- Main App Routes -------------------
app.get('/', (req, res) => res.redirect('/dashboard'));

app.get('/dashboard', checkAuth, checkInterstitial, (req, res) => {
  const postedCount = database.invoices.filter(i => i.status === 'POSTED').length;
  const unpaidCount = database.invoices.filter(i => i.status === 'UNPAID').length;

  const body = `
    <div class="card">
      <h2>Accounts Payable Overview</h2>
      <p>Welcome, <strong>${req.user.username}</strong>. CentraERP is operational.</p>
      <div style="display: flex; gap: 20px; margin-top: 15px;">
        <div style="background: #eff6ff; padding: 15px; border-radius: 6px; flex: 1;">
          <div style="font-size: 24px; font-weight: bold; color: #1e40af;">${database.invoices.length}</div>
          <div style="color: #64748b;">Total Invoices in Ledger</div>
        </div>
        <div style="background: #f0fdf4; padding: 15px; border-radius: 6px; flex: 1;">
          <div style="font-size: 24px; font-weight: bold; color: #166534;">${postedCount}</div>
          <div style="color: #64748b;">Posted / Settled</div>
        </div>
        <div style="background: #fffbeb; padding: 15px; border-radius: 6px; flex: 1;">
          <div style="font-size: 24px; font-weight: bold; color: #92400e;">${unpaidCount}</div>
          <div style="color: #64748b;">Pending Review / Unpaid</div>
        </div>
      </div>
    </div>
  `;
  res.send(renderPage('Dashboard', body, req.user));
});

// Invoices Ledger Page
app.get('/invoices', checkAuth, checkInterstitial, (req, res) => {
  const vendorFilter = req.query.vendor;
  let list = database.invoices;
  if (vendorFilter) {
    list = list.filter(i => i.vendor.toLowerCase().includes(vendorFilter.toLowerCase()));
  }

  const rows = list.map(inv => `
    <tr id="row-${inv.invoice_number}">
      <td><strong>${inv.invoice_number}</strong></td>
      <td>${inv.vendor}</td>
      <td>$${Number(inv.amount).toFixed(2)}</td>
      <td>${inv.po_number || 'N/A'}</td>
      <td>${inv.due_date}</td>
      <td><span class="badge badge-${inv.status.toLowerCase()}">${inv.status}</span></td>
      <td>${inv.flagged_for_review ? '<span class="badge badge-flagged">FLAGGED</span>' : 'Normal'}</td>
    </tr>
  `).join('');

  const body = `
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <h2>Invoices General Ledger</h2>
        <a id="btn-new-invoice" href="/invoices/new" style="background: #2563eb; color: #fff; padding: 8px 14px; border-radius: 4px; text-decoration: none; font-size: 14px; font-weight: 600;">+ Record New Invoice</a>
      </div>
      <table id="table-invoices">
        <thead>
          <tr>
            <th>Invoice #</th>
            <th>Vendor</th>
            <th>Amount</th>
            <th>PO Reference</th>
            <th>Due Date</th>
            <th>Status</th>
            <th>Review Status</th>
          </tr>
        </thead>
        <tbody>
          ${rows || '<tr><td colspan="7">No invoices found.</td></tr>'}
        </tbody>
      </table>
    </div>
  `;
  res.send(renderPage('Invoices Ledger', body, req.user));
});

// New Invoice Entry Form
app.get('/invoices/new', checkAuth, checkInterstitial, (req, res) => {
  const activeFaults = faults.getFaults();
  const csrfToken = crypto.randomBytes(16).toString('hex');
  res.cookie('centra_csrf', csrfToken);

  // Fault: renamed_field changes invoice_number input name to invoice_ref_no
  const invFieldName = activeFaults.renamed_field ? 'invoice_ref_no' : 'invoice_number';
  const invFieldLabel = activeFaults.renamed_field ? 'Invoice Reference Number (Ref ID)' : 'Invoice Number';

  const body = `
    <div class="card" style="max-width: 600px;">
      <h2>Record Accounts Payable Invoice</h2>
      <p style="color: #64748b; font-size: 14px;">Enter verified vendor invoice details. Ensure referenced PO has sufficient remaining balance.</p>
      <form id="form-invoice-entry" method="POST" action="/invoices">
        <input type="hidden" name="csrf_token" value="${csrfToken}" />
        <div class="form-group">
          <label for="vendor">Vendor Name *</label>
          <input type="text" id="vendor" name="vendor" required placeholder="e.g. Acme Corporation" />
        </div>
        <div class="form-group">
          <label for="${invFieldName}">${invFieldLabel} *</label>
          <input type="text" id="${invFieldName}" name="${invFieldName}" required placeholder="e.g. INV-2041" />
        </div>
        <div class="form-group">
          <label for="amount">Invoice Total Amount ($ USD) *</label>
          <input type="number" step="0.01" id="amount" name="amount" required placeholder="1200.00" />
        </div>
        <div class="form-group">
          <label for="po_number">Purchase Order Reference *</label>
          <input type="text" id="po_number" name="po_number" required placeholder="e.g. ACM-892" />
        </div>
        <div class="form-group">
          <label for="due_date">Payment Due Date *</label>
          <input type="text" id="due_date" name="due_date" required placeholder="YYYY-MM-DD" />
        </div>
        <button id="btn-submit-invoice" type="submit">Post Invoice to Ledger</button>
      </form>
    </div>
  `;
  res.send(renderPage('New Invoice Entry', body, req.user));
});

// Post Invoice Form Handler
app.post('/invoices', checkAuth, checkInterstitial, async (req, res) => {
  const activeFaults = faults.getFaults();

  // Fault: slow_response
  if (activeFaults.slow_response) {
    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  const vendor = req.body.vendor?.trim();
  const invoiceNumber = (req.body.invoice_number || req.body.invoice_ref_no)?.trim();
  const amount = parseFloat(req.body.amount);
  const poNumber = req.body.po_number?.trim();
  const dueDate = req.body.due_date?.trim();

  // Validation: Missing fields
  if (!vendor || !invoiceNumber || isNaN(amount) || !poNumber || !dueDate) {
    const errorBody = `
      <div class="card" style="max-width: 500px;">
        <div class="alert-error" id="form-validation-error">All fields are required. Please check your submission.</div>
        <a href="/invoices/new">Back to Invoice Entry</a>
      </div>
    `;
    return res.status(400).send(renderPage('Validation Error', errorBody, req.user));
  }

  // Fault: date_format_error requires strict YYYY-MM-DD
  if (activeFaults.date_format_error) {
    const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateRegex.test(dueDate)) {
      const errorBody = `
        <div class="card" style="max-width: 500px;">
          <div class="alert-error" id="date-format-error">Invalid Date Format. CentraERP strictly requires format YYYY-MM-DD (Received: ${dueDate}).</div>
          <a href="/invoices/new">Correct Date Format</a>
        </div>
      `;
      return res.status(422).send(renderPage('Format Error', errorBody, req.user));
    }
  }

  // Idempotency / Duplicate Check
  const exists = database.invoices.find(i => i.vendor.toLowerCase() === vendor.toLowerCase() && i.invoice_number.toUpperCase() === invoiceNumber.toUpperCase());
  if (exists || activeFaults.duplicate_trap) {
    const errorBody = `
      <div class="card" style="max-width: 500px;">
        <div class="alert-error" id="duplicate-invoice-error">Duplicate invoice detected: Vendor "${vendor}" already has an invoice with number "${invoiceNumber}" recorded in ledger. Duplicate posting prohibited.</div>
        <a href="/invoices">View Invoices Ledger</a>
      </div>
    `;
    return res.status(409).send(renderPage('Duplicate Error', errorBody, req.user));
  }

  // Fault: lying_success renders a success page but deliberately does NOT write to database!
  if (activeFaults.lying_success) {
    const lyingBody = `
      <div class="card" style="max-width: 600px;">
        <div class="alert-success" id="post-success-banner">Invoice recorded successfully in general ledger!</div>
        <p>Transaction Reference: <strong>TXN-MOCK-LYING-999</strong></p>
        <p>Vendor: <strong>${vendor}</strong> | Invoice: <strong>${invoiceNumber}</strong> | Amount: <strong>$${amount.toFixed(2)}</strong></p>
        <a href="/invoices">Return to Invoices Ledger</a>
      </div>
    `;
    return res.send(renderPage('Invoice Posted', lyingBody, req.user));
  }

  // Genuine Successful Write Path
  const txnId = 'TXN-' + crypto.randomBytes(6).toString('hex').toUpperCase();
  const newInvoice = {
    id: txnId,
    vendor,
    invoice_number: invoiceNumber,
    amount,
    po_number: poNumber,
    due_date: dueDate,
    status: 'POSTED',
    flagged_for_review: false,
    created_at: new Date().toISOString()
  };
  database.invoices.push(newInvoice);

  const successBody = `
    <div class="card" style="max-width: 600px;">
      <div class="alert-success" id="post-success-banner">Invoice ${invoiceNumber} successfully posted to General Ledger!</div>
      <p>Transaction ID: <strong id="txn-id">${txnId}</strong></p>
      <p>Vendor: <strong>${vendor}</strong></p>
      <p>Amount: <strong>$${amount.toFixed(2)} USD</strong></p>
      <p>Status: <span class="badge badge-posted">POSTED</span></p>
      <a id="link-ledger-verify" href="/invoices">Return to Invoices Ledger</a>
    </div>
  `;
  res.send(renderPage('Invoice Posted', successBody, req.user));
});

// PO Ledger Page
app.get('/po', checkAuth, checkInterstitial, (req, res) => {
  const rows = database.pos.map(po => `
    <tr id="row-${po.po_number}">
      <td><strong>${po.po_number}</strong></td>
      <td>${po.vendor}</td>
      <td>$${po.amount.toFixed(2)} ${po.currency}</td>
      <td><span class="badge badge-open">${po.status}</span></td>
      <td>${po.line_items.join(', ')}</td>
    </tr>
  `).join('');

  const body = `
    <div class="card">
      <h2>Purchase Order (PO) Commitments Ledger</h2>
      <table id="table-po">
        <thead>
          <tr>
            <th>PO Number</th>
            <th>Authorized Vendor</th>
            <th>Committed Total</th>
            <th>Status</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>
  `;
  res.send(renderPage('PO Ledger', body, req.user));
});

// ------------------- Read-Only Verification API -------------------
// Verification uses a separate read-only path with a read-only token
function checkApiAuth(req, res, next) {
  const authHeader = req.headers['authorization'];
  if (!authHeader || authHeader !== `Bearer ${READ_ONLY_TOKEN}`) {
    return res.status(401).json({ error: 'Unauthorized: Read-only audit bearer token required' });
  }
  next();
}

app.get('/api/invoices', checkApiAuth, (req, res) => {
  let list = database.invoices;
  if (req.query.vendor) {
    list = list.filter(i => i.vendor.toLowerCase().includes(req.query.vendor.toLowerCase()));
  }
  if (req.query.invoice_number) {
    list = list.filter(i => i.invoice_number.toUpperCase() === req.query.invoice_number.toUpperCase());
  }
  if (req.query.status) {
    list = list.filter(i => i.status.toUpperCase() === req.query.status.toUpperCase());
  }
  res.json({
    count: list.length,
    invoices: list
  });
});

app.get('/api/po', checkApiAuth, (req, res) => {
  let list = database.pos;
  if (req.query.po_number) {
    list = list.filter(p => p.po_number.toUpperCase() === req.query.po_number.toUpperCase());
  }
  res.json({
    count: list.length,
    pos: list
  });
});

// Generalization Review Flag Endpoint
app.post('/api/invoices/:id/flag', checkApiAuth, (req, res) => {
  const inv = database.invoices.find(i => i.id === req.params.id || i.invoice_number === req.params.id);
  if (!inv) return res.status(404).json({ error: 'Invoice not found' });
  inv.flagged_for_review = true;
  inv.review_note = req.body.note || 'Flagged for aging review >30 days';
  res.json({ status: 'ok', invoice: inv });
});

app.listen(PORT, () => {
  console.log(`[CentraERP] Server running on http://localhost:${PORT}`);
});
