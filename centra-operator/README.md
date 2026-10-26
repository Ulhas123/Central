# CentraOperator: Autonomous Enterprise Company Operator

**Candidate:** Varun Karankar (IIIT Allahabad)  
**Role:** Founding Engineer — CentrAlign AI  
**Domain:** Autonomous Finance & Accounts Payable Operations  
**Architecture Dossier:** [`CentraOperator_Architecture_Dossier.pdf`](../CentraOperator_Architecture_Dossier.pdf)

---

## Executive Summary

CentraOperator transforms an unscripted, natural language operational objective from an enterprise finance team (e.g., *"Process the latest Acme invoice and match it to its PO"*) into completed, cryptographically verified enterprise transactions. It operates autonomously across internal enterprise web portals, follows company standard operating procedures (SOPs), deterministically triggers human-in-the-loop oversight when financial thresholds are exceeded, and independently verifies outcomes via an isolated database read path before declaring success.

---

## 1. Setup and Run Instructions

### 1.1 Prerequisites
- **Python:** 3.10+ (tested on Python 3.12)
- **Node.js:** 18+ & npm
- **Operating System:** Windows, macOS, or Linux

---

### 1.2 Quickstart: Automated Test Suite (No Services Required)
The test suite validates the core agent primitives (deterministic policy gates, idempotency locks, LangGraph checkpoint resumption, CSRF web-form sessions, and the independent verifier) completely in-memory:

```bash
# From repository root or centra-operator/
python -m unittest discover tests
```
*Expected Output:* `Ran 10 tests in ~0.14s ... OK`

---

### 1.3 Quickstart: Evaluation Benchmark Suite Across Fault Matrix
The evaluation harness tests the agent against a simulated enterprise environment with live environmental fault injection (session timeouts, interstitial banners, lying UI banners, and generalization tasks):

**Step 1: Start CentraERP (Simulated Enterprise Portal)**
```bash
cd services/erp
node server.js
```
*Runs on `http://localhost:4000`.*

**Step 2: Run Automated Evaluation Harness (Second Terminal)**
```bash
python eval/run_eval.py
```
*Empirical Output:*
- Task Success Rate: **5/5 (100.0%)**
- Silent UI Failures Caught: **1/1 (100.0%)**
- Duplicate Writes: **0 (Zero-Tolerance Guardrail Met)**
- Execution Latency: **< 0.10s per task**

---

### 1.4 Full Stack Mission Control Dashboard (Interactive Web UI)
To run the full distributed stack with the React Mission Control dashboard, real-time WebSocket telemetry, and interactive Human-in-the-Loop approval cards:

1. **CentraERP (Target System):**
   ```bash
   cd services/erp
   node server.js
   ```
   *(Port 4000)*

2. **Agent Runtime (FastAPI + LangGraph Engine):**
   ```bash
   cd services/runtime
   python main.py
   ```
   *(Port 8000)*

3. **API Gateway & Socket Relay (Node.js + Express + TypeScript):**
   ```bash
   cd services/gateway
   npm start
   ```
   *(Port 3000)*

4. **Mission Control Dashboard (React + Vite + Socket.IO):**
   ```bash
   cd services/dashboard
   npm run dev
   ```
   *(Opens on `http://localhost:5173`)*

---

## 2. Short Explanation of the Architecture

CentraOperator is designed around an **8-stage cyclical execution graph** with dynamic feedback and self-healing edges:

```
[Goal] ──> [Understand] ──> [Recall] ──> [Plan] ──> [Gate] ──> [Act] ──> [Observe] ──> [Adapt] ──> [Verify] ──> [Complete]
                                           ^                        │           │         │
                                           └────────────────────────┴───────────┴─────────┘
                                                (Re-plan on dynamic feedback or failed verification)
```

### Microservice Decoupling
1. **React Mission Control Dashboard (`services/dashboard`):** Real-time execution visualizer displaying live state transitions, action traces, interactive Human-in-the-Loop approval cards, and cryptographic evidence.
2. **API Gateway & Relay (`services/gateway`):** Orchestrates tasks via BullMQ and Redis, and streams state changes to the UI via Socket.IO.
3. **Agent Runtime Core (`services/runtime`):** LangGraph execution engine managing task state, Qdrant episodic memory, deterministic policy gates, and tool dispatch.
4. **CentraERP (`services/erp`):** Realistic enterprise web application featuring server-rendered forms, session authentication, CSRF tokens, pagination, and toggleable fault injection.

### Generic State Representation (`RunState`)
The runtime state is completely domain-agnostic. It contains **zero invoice-specific keys**:
```python
class RunState(TypedDict):
    task_id: str
    company_id: str
    goal: str
    criteria: list[dict]        # Machine-checkable acceptance assertions
    facts: dict[str, Any]       # Dynamic discovered knowledge & IDs
    policies: list[dict]        # SOPs with executable rule schemas
    memories: list[dict]        # Precedent from past human decisions
    plan: list[dict]            # Revisable queue of intended actions
    pending_action: dict | None
    last_observation: dict | None
    history: list[dict]         # Append-only execution trace
    attempts: dict[str, int]    # Per-action retry counts
    budget: dict                # max_steps, max_retries limits
    verification: dict | None   # Isolated read-path audit results
    status: str
    evidence: list[dict]
```

---

## 3. Important Technical & Design Decisions

### 3.1 Policy as Data, Enforcement as Code
- **The Problem:** LLMs are probabilistic engines. Asking an LLM in a prompt to "remember not to approve invoices over $5,000" causes catastrophic hallucinations under context pressure.
- **Our Decision:** Policies stored in Qdrant combine semantic descriptions with **structured rule payloads** (e.g., `{"field": "amount", "op": "gt", "value": 5000, "action": "require_approval"}`). The `gate_node` evaluates these rules deterministically in native code. When triggered, the graph invokes LangGraph's `interrupt()`, checkpoints state, and emits an approval request.

### 3.2 Independent Read-Path Verification (Catching the "Lying UI")
- **The Problem:** Enterprise web forms frequently return misleading `200 OK` responses or render green "Success" banners even when the database transaction failed or silently rolled back.
- **Our Decision:** CentraOperator mutates state through UI forms, but **verifies completion strictly through an isolated, read-only JSON API using an isolated read-only bearer token**. It executes machine assertions on raw database records (`status == 'POSTED'`, `amount == source_amount`). If the UI lied, verification fails, routing control to `Adapt` for recovery or honest escalation.

### 3.3 Protocol-Level Web Automation (Deterministic & Browserless)
- **The Problem:** Heavy browser engines (Playwright/Puppeteer) introduce massive binary overhead, flaky selector timeouts, and non-deterministic DOM waits.
- **Our Decision:** The web tool operates at the HTTP protocol layer using Python's standard library (`urllib.request`, `http.cookiejar`, `html.parser`). It models pages as accessibility-style DOM trees (forms, tables, CSRF tokens, error banners) and automates session management without headless browser dependencies.

### 3.4 Defense-in-Depth Idempotency
- **The Problem:** Network timeouts or task restarts in finance can trigger catastrophic duplicate vendor payments.
- **Our Decision:** Three-tier idempotency:
  1. *Tool-Level Lock:* Redis atomic key `sha256(operation : vendor : invoice_number)` with TTL.
  2. *Read-Before-Retry:* On ambiguous network timeouts, the agent queries the read-only ERP API to check if the record exists before re-submitting.
  3. *ERP Database Constraint:* Unique compound index on `(vendor, invoice_number)`.

### 3.5 Least-Privilege Credential Boundary
- **The Problem:** Injecting raw passwords or master API keys into LLM context windows creates prompt injection and exfiltration vulnerabilities.
- **Our Decision:** The LLM only receives opaque credential identifiers (e.g., `credential_ref: "erp_ap_clerk"`). The underlying tool execution layer injects the actual secrets at the network boundary.

### 3.6 Episodic Memory from Human Feedback
- Human approval, rejection, and override decisions are embedded and indexed in Qdrant. Future approval requests cite institutional precedent (e.g., *"Past Precedent: Two earlier invoices from Acme Corp exceeding $5,000 were approved by the Finance Director"*), assisting human reviewers without bypassing policy gates.

### 3.7 Tamper-Evident SHA-256 Audit Chain
- Every action, observation, gate decision, and verification result is linked in an append-only cryptographic hash chain (`hash = sha256(prev_hash + canonical_json(event))`). Any post-hoc modification to the audit trail immediately breaks integrity verification.

---

## 4. Demo Video Script (2.5 - 3 Minutes)

> **Instructions for Recording:** Keep screen split with the Mission Control Dashboard on the left (`http://localhost:5173`) and a terminal running `python eval/run_eval.py` on the right.

### Scene 1: Introduction & System Overview (0:00 - 0:35)
- **Visual:** Full screen showing CentraOperator Dashboard with system services connected (ERP: 4000, Gateway: 3000, Runtime: 8000).
- **Voiceover:**
  > *"Hello! Today I'm presenting **CentraOperator**, an autonomous enterprise company operator engineered for the CentrAlign AI Founding Engineer role.  
  > Enterprise AI must evolve beyond chatbots that merely suggest text to autonomous workers that understand company goals, use enterprise tools, follow company SOPs, verify their own work, and ask for human approval only when required.  
  > CentraOperator executes an 8-stage cyclical state machine: Goal, Understand, Recall, Plan, Gate, Act, Observe, Adapt, and Verify—anchored by deterministic policy code and independent read-path verification."*

### Scene 2: Scenario 1 — Autonomous Happy Path (0:35 - 1:15)
- **Visual:** Click **"1. 🟢 Happy Path: Process Acme invoice ($1,200) & PO match"**. Point cursor at the execution trace as it animates.
- **Voiceover:**
  > *"In this first scenario, the operator receives an unscripted goal: 'Process the latest Acme invoice and match it to its PO'.  
  > First, the agent reads the raw document from the inbox and extracts the vendor, amount ($1,200), and PO number.  
  > Next, in `Recall`, it queries semantic SOPs from Qdrant and checks financial approval limits. Since $1,200 is below the $5,000 threshold, it passes the Gate automatically.  
  > In `Plan` and `Act`, it navigates CentraERP, submits the invoice entry form with CSRF handling, and logs into the portal.  
  > Crucially, look at `Verify`: the agent does NOT trust the web page's success alert. It queries the isolated read-only JSON API using a separate audit token, verifies the record is posted with exact matching amounts, and seals the event into a tamper-evident SHA-256 hash chain."*

### Scene 3: Scenario 2 — Deterministic Policy Gate & HITL Resumption (1:15 - 2:00)
- **Visual:** Click **"2. 🟡 Policy Approval: Apex Global ($14,500) triggers HITL Limit Gate"**. Show the execution pause and the interactive Approval Card appear.
- **Voiceover:**
  > *"Now, let's test company policy boundaries. Apex Global submits an invoice for $14,500.  
  > Notice that execution halts immediately at the `Gate` node. This guardrail is not left to LLM chance—our code deterministically evaluated the structured rule schema from `sop_ap_limits.json`.  
  > The graph pauses, checkpoints its state, and pushes an approval card to our dashboard.  
  > Notice the card cites **Episodic Memory**: 'Precedent: Two earlier invoices from this vendor over the limit were approved by the CFO'.  
  > When I click **'Approve with Override'**, the graph resumes from its exact checkpoint, completes the ERP submission, verifies database persistence, and records this approval back into episodic memory."*

### Scene 4: Scenario 3 — Environmental Fault Matrix & Lying UI Caught (2:00 - 2:40)
- **Visual:** Switch focus to the terminal. Run `python eval/run_eval.py`. Highlight the benchmark table and `task_4_lying_ui_caught`.
- **Voiceover:**
  > *"To validate production reliability, we built an automated evaluation harness with an environmental fault matrix.  
  > Look at `task_4_lying_ui_caught`. Here, CentraERP triggers a `lying_success` fault: the web page displays a deceptive green 'Invoice recorded successfully' banner, but deliberately discards the database write.  
  > A naive agent would read the banner and falsely report success. CentraOperator's independent read-path verifier checks the true database state, detects the missing record, triggers the `Adapt` cycle, and escalates honestly with cryptographic evidence.  
  > Across all 5 benchmark tasks, CentraOperator achieved 100% verified task success, caught 100% of silent UI failures, and recorded zero duplicate writes."*

### Scene 5: Conclusion & Generalization (2:40 - 3:00)
- **Visual:** Return to dashboard, show Helios Systems Aging Review completion.
- **Voiceover:**
  > *"Finally, task 5 demonstrates true domain generalization: the agent completed a vendor aging ledger review with zero Python code changes, driven purely by declarative SOPs.  
  > CentraOperator delivers deterministic reliability, least-privilege security, and rigorous verification—the exact foundation required for enterprise AI employees. Thank you!"*

---

## 5. Known Limitations

1. **Protocol-Level Web Interaction:** Uses Python standard library HTML parsers and cookie jars for server-rendered web applications. It does not execute client-side JavaScript Single Page Apps (React/Angular) or drive native desktop GUI windows. (Designed as an abstraction so Playwright or OS-level Computer Use drivers slot in behind identical tool schemas).
2. **Semi-Structured Document Ingestion:** Currently ingests plain-text invoices and email notices from `data/inbox/`. It does not include an optical character recognition (OCR) or visual PDF parsing pipeline.
3. **Simulated Enterprise Portal:** CentraERP runs locally. While it mimics realistic enterprise conditions (CSRF tokens, session timeouts, interstitial banners, and DB unique constraints), it does not encounter production network latency spikes or arbitrary DOM variations.
4. **Single-Tenant Policy Context:** The prototype evaluates policies and episodic memory within a single enterprise tenant environment. Multi-tenant keying and namespace isolation are designed but not deployed.
5. **Tamper-Evident vs. Cryptographically Signed Audit Logs:** The audit trail uses SHA-256 hash chaining to detect modifications, but does not yet employ public-private keypairs (e.g., Ed25519) to provide non-repudiable digital signatures.

---

## 6. What I Would Build Next (Founding Engineer Roadmap)

1. **Headless Browser & Computer-Use Driver Slot-in:** Implement a Playwright adapter and an OS-level Computer Use driver implementing the existing `web_open` and `web_submit` tool schemas to operate complex SPA dashboards and legacy desktop ERP clients (e.g., SAP GUI).
2. **Multimodal Document Pipeline:** Add a document processing worker supporting native PDF vector extraction, scanned image OCR, and table extraction with bounding-box verification.
3. **Multi-Tenant Isolation & Partitioned Vaults:** Implement company-scoped vector namespaces in Qdrant, row-level tenant security, and an external secret vault (e.g., HashiCorp Vault) for credential injection.
4. **Hierarchical Multi-Level Approval Routing:** Support multi-tier approval matrixes with configurable escalation timeouts, Slack/Teams webhooks, and out-of-office delegation workflows.
5. **Automated Policy Learning & Distillation:** Periodically mine episodic memory for recurring human approval overrides to automatically draft and propose new candidate SOP rules for executive sign-off.
6. **Non-Repudiable Cryptographic Audit Receipts:** Upgrade hash chains to asymmetric Ed25519 digital signatures and stream audit proofs to immutable external syslog targets.

---

## 7. Assumptions Made While Building the Solution

1. **Legacy Web Portal Predominance:** Assumed target enterprise systems often lack complete, documented REST APIs, making browser-like web form interaction necessary for operational execution.
2. **Deterministic Role Hierarchy:** Assumed a single Human-in-the-Loop approver role (e.g., Finance Director / AP Manager) authorized to approve financial threshold exceptions from the dashboard.
3. **Document Ingestion Format:** Assumed incoming vendor invoices and billing communications arrive in a monitored file store or inbox in UTF-8 plain-text format.
4. **Clock Synchronization:** Assumed synchronized UTC system clocks across the agent runtime, API gateway, and target enterprise ERP.
5. **Zero-Tolerance for Duplicate Financial Writes:** Assumed duplicate invoice postings or payments carry severe financial risk, justifying strict Redis lock keying and read-before-retry safeguards.

---

## 8. Models, APIs, Frameworks, and Pre-built Components Used

| Category | Component / Tool | Version / Details | Purpose in Solution |
|---|---|---|---|
| **Core Runtime & Graph** | Python | 3.12 | Primary agent execution runtime |
| | LangGraph | 0.2.x | Cyclical state graph, checkpointer, and `interrupt()` HITL engine |
| | FastAPI & Uvicorn | 0.110.x | High-throughput agent execution microservice & REST API |
| **API Gateway & Relay** | Node.js & TypeScript | Node 18+, TS 5.4 | Enterprise API gateway, request validation, and types |
| | Express | 4.19.x | Gateway REST server & CentraERP application server |
| | Socket.IO & socket.io-client | 4.7.x | Bidirectional real-time telemetry and approval event streaming |
| | BullMQ & IORedis | BullMQ 5.4, IORedis 5.3 | Distributed task queue, worker scheduling, and retry management |
| **Memory & Databases** | Qdrant | In-Memory / Vector DB | Semantic search for company SOPs and episodic feedback retrieval |
| | MongoDB & Change Streams | 6.0+ | Persistent state checkpointer, audit storage, and reactive event push |
| | Redis | 7.x / IORedis | Distributed idempotency locking and BullMQ backing store |
| **Frontend Dashboard** | React & ReactDOM | 18.2.0 | Reactive Mission Control operator interface |
| | Vite | 5.1.x | Lightning-fast frontend build tooling and HMR |
| **Security & Standards** | SHA-256 Hashing | Python `hashlib` / Node `crypto` | Idempotency key fingerprinting and tamper-evident audit chaining |
| | CookieJar & HTMLParser | Python `urllib`, `http.cookiejar` | Deterministic, headless-free web form session automation |
| **AI Models (Designed Integration)** | OpenAI API / Local Fallbacks | `gpt-4o` / text-embedding-3-small | Semantic goal understanding, SOP embedding, and anomaly explanation |

---

## 9. Verification & Submission Dossier

- **Complete Technical Specification:** See [`CentraOperator_Architecture_Dossier.pdf`](../CentraOperator_Architecture_Dossier.pdf) for a 30-page mathematical formalization, LaTeX architecture schemas, and fault recovery proofs.
- **Automated Test Suite:** Discoverable under `tests/` (10 passing tests).
- **Automated Evaluation Benchmark:** Executable via `python eval/run_eval.py` across 5 fault injection tasks.
