# CentraOperator: Live Demo & Interview Walkthrough Guide
**Audience:** CentrAlign AI Technical Founders & Hiring Team  
**Presenter:** Varun Karankar  
**Duration:** 3–5 minutes

---

## Demo Script

### 1. Introduction (30 seconds)
> *"Hello! Today I'm presenting **CentraOperator**, a prototype of an autonomous enterprise company operator for accounts payable and procurement, engineered using a high-performance distributed stack: FastAPI, LangGraph, Qdrant, Express, BullMQ, Redis, React, and Socket.IO.*
>
> *CentrAlign's problem statement emphasizes moving past conversational chatbots to autonomous execution of company workflows with minimal supervision. To prove this, CentraOperator implements the full loop:*  
> **Goal → Understand → Recall → Plan → Gate → Act → Observe → Adapt → Verify → Complete**  
> *with independent read-path verification and deterministic policy guardrails."*

---

### 2. Scenario 1: The Happy Path (45 seconds)
1. **Action:** Click button **"1. 🟢 Happy Path: Process Acme invoice ($1,200) & PO match"** in the Dashboard.
2. **Talking Points while it runs:**
   - *"The operator reads the plain-text Acme invoice from the inbox, extracting the vendor, amount ($1,200), and PO #ACM-892."*
   - *"In `Recall`, it queries Qdrant for SOPs and checks company approval limits ($1,200 < $5,000 threshold).*
   - *"In `Plan` and `Act`, it navigates to CentraERP, submits the invoice entry form using protocol-level web automation (least-privilege credential injection), and captures the transaction ID."*
   - *"Notice in `Verify`: rather than trusting the web form's success message, it queries the read-only JSON API using an isolated read-only bearer token, confirming the database record status is 'POSTED' and amount matches exactly."*
   - *"Finally, it seals the event into a tamper-evident SHA-256 hash chain."*

---

### 3. Scenario 2: Policy Guardrail & HITL Resumption (1 minute)
1. **Action:** Click button **"2. 🟡 Policy Approval: Apex Global ($14,500) triggers HITL Limit Gate"**.
2. **Talking Points:**
   - *"Apex Global submitted an invoice for $14,500 for a security appliance."*
   - *"Notice the graph pauses immediately at the `Gate` node! It doesn't guess or ask the LLM to remember a number: our gate code deterministically evaluated `amount > 5,000` from `sop_ap_limits.json`."*
   - *"LangGraph checkpoints its state, emits an interrupt over Socket.IO, and renders this interactive Approval Card on the dashboard."*
   - *"Notice the card cites **Episodic Memory** from Qdrant: 'Two earlier invoices from this vendor over the limit were approved by the CFO'. Institutional memory informs human decisions without silently bypassing security rules."*
3. **Action:** Click **"✓ Approve with Override"**.
4. **Talking Points:**
   - *"Upon approval, the gateway posts to `/api/approvals`, LangGraph resumes execution from the exact checkpoint without re-reading the document, posts to CentraERP, verifies the record, and records this human decision back into episodic memory."*

---

### 4. Scenario 3: Lying UI Caught & Self-Healing (1 minute)
1. **Action:** Show the automated evaluation harness output in the terminal:
   ```bash
   python eval/run_eval.py
   ```
2. **Talking Points:**
   - *"To prove genuine reliability, we built an environmental fault matrix in CentraERP."*
   - *"Look at `task_4_lying_ui_caught`: CentraERP has a fault called `lying_success`, where the web page displays a green 'Invoice recorded successfully' banner, but deliberately fails to persist anything in the database."*
   - *"An ordinary agent would read the banner and report success. CentraOperator's independent verifier checks the database via `/api/invoices`, detects the record is missing, catches the false positive, loops into `Adapt`, and escalates honestly."*

---

### 5. Scenario 4: Generalization with Zero Code Changes (45 seconds)
1. **Action:** Click button **"3. 🔵 Generalization Task: Helios Systems Aging Review"**.
2. **Talking Points:**
   - *"To prove that this isn't an overfitted AP script, task 5 gives the agent a completely different request: 'List unpaid invoices older than 30 days for vendor Helios and flag them for review'."*
   - *"Without modifying a single line of Python, the exact same runtime reads the aging SOP from Qdrant, identifies overdue accounts, flags them in CentraERP, and independently verifies the flags."*

---

### 6. Closing (30 seconds)
> *"CentraOperator delivers 100% verified task success, zero duplicate writes, deterministic policy guardrails, and cryptographic auditability—built end-to-end to demonstrate what a production-grade Founding Engineer brings to CentrAlign AI. Thank you!"*
