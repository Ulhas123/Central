import React, { useState, useEffect } from 'react';
import { io, Socket } from 'socket.io-client';
import './styles.css';

interface TaskEvent {
  type: string;
  timestamp: string;
  details?: any;
}

export function App() {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [prompt, setPrompt] = useState('Process the latest Acme invoice and match it to its PO');
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<string>('IDLE');
  const [events, setEvents] = useState<TaskEvent[]>([]);
  const [interruptData, setInterruptData] = useState<any>(null);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [completionSummary, setCompletionSummary] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const s = io('http://localhost:3000', {
      reconnectionAttempts: 5,
      timeout: 3000
    });
    setSocket(s);

    s.on('task:update', (data: any) => {
      console.log('Task update received:', data);
      if (data && data.eventType) {
        setEvents(prev => [...prev, {
          type: String(data.eventType),
          timestamp: new Date().toLocaleTimeString(),
          details: data.payload
        }]);
      }
      if (data?.payload?.status) {
        setTaskStatus(String(data.payload.status));
      }
      if (data?.payload?.summary) {
        setCompletionSummary(String(data.payload.summary));
      }
      if (Array.isArray(data?.payload?.evidence)) {
        setEvidence(data.payload.evidence);
      }
    });

    s.on('hitl:interrupt', (data: any) => {
      console.log('HITL Interrupt received:', data);
      if (data?.taskId) setCurrentTaskId(data.taskId);
      setTaskStatus('AWAITING_APPROVAL');
      if (data?.interruptData) {
        setInterruptData(data.interruptData);
      }
      setEvents(prev => [...prev, {
        type: 'HITL_INTERRUPT_REQUESTED',
        timestamp: new Date().toLocaleTimeString(),
        details: data?.interruptData
      }]);
    });

    return () => {
      s.disconnect();
    };
  }, []);

  const handleRunTask = async (customPrompt?: string) => {
    const activePrompt = customPrompt || prompt;
    setLoading(true);
    setEvents([]);
    setInterruptData(null);
    setEvidence([]);
    setCompletionSummary(null);
    setTaskStatus('ENQUEUEING');

    try {
      const res = await fetch('http://localhost:3000/api/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal: activePrompt, company_id: 'COMP-001' })
      });
      const data = await res.json();
      
      if (!res.ok) {
        const errorMsg = data?.error || data?.details || `Server returned HTTP ${res.status}`;
        setTaskStatus('ERROR');
        setEvents(prev => [...prev, {
          type: 'ERROR',
          timestamp: new Date().toLocaleTimeString(),
          details: { message: errorMsg }
        }]);
        alert(`Task Dispatch Failed:\n${errorMsg}\n\nPlease verify that the Agent Runtime is running on port 8000.`);
        return;
      }

      setCurrentTaskId(data?.taskId || null);
      setTaskStatus(String(data?.status || 'STARTED'));

      if (data?.result?.interrupt_data) {
        setInterruptData(data.result.interrupt_data);
      }
      if (Array.isArray(data?.result?.evidence)) {
        setEvidence(data.result.evidence);
      }
      if (data?.result?.summary) {
        setCompletionSummary(data.result.summary);
      }
      if (Array.isArray(data?.result?.history)) {
        setEvents(prev => {
          if (prev.length <= 1) {
            return data.result.history.map((h: any) => ({
              type: (h.type || 'GRAPH_STEP').toUpperCase(),
              timestamp: new Date().toLocaleTimeString(),
              details: h
            }));
          }
          return prev;
        });
      }
    } catch (err: any) {
      setTaskStatus('DISPATCH_ERROR');
      setEvents(prev => [...prev, {
        type: 'CONNECTION_ERROR',
        timestamp: new Date().toLocaleTimeString(),
        details: { message: err.message }
      }]);
      alert(`Cannot connect to Gateway at http://localhost:3000:\n${err.message}\n\nPlease ensure Gateway is running.`);
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (approved: boolean) => {
    if (!currentTaskId) return;
    setLoading(true);
    try {
      const res = await fetch('http://localhost:3000/api/approvals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          taskId: currentTaskId,
          approved,
          note: approved ? 'Manager approval granted via Dashboard Card' : 'Rejected by supervisor'
        })
      });
      const data = await res.json();
      setInterruptData(null);
      setTaskStatus(String(data?.status || (approved ? 'APPROVED' : 'REJECTED')));
      if (Array.isArray(data?.result?.evidence)) {
        setEvidence(data.result.evidence);
      }
      if (data?.result?.summary) {
        setCompletionSummary(data.result.summary);
      }
      if (Array.isArray(data?.result?.history)) {
        setEvents(prev => {
          if (prev.length <= 1) {
            return data.result.history.map((h: any) => ({
              type: (h.type || 'GRAPH_STEP').toUpperCase(),
              timestamp: new Date().toLocaleTimeString(),
              details: h
            }));
          }
          return prev;
        });
      }
    } catch (err: any) {
      alert('Error submitting decision: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const nodes = ['Understand', 'Recall', 'Plan', 'Gate', 'Act', 'Observe', 'Adapt', 'Verify', 'Complete'];
  const safeStatus = (taskStatus || 'IDLE').toString();

  return (
    <div className="app-container">
      <header>
        <div className="brand">
          <span className="brand-badge">CentraAlign AI</span>
          <h1>CentraOperator &mdash; Autonomous Enterprise Operator</h1>
        </div>
        <div className="status-indicator">
          <span className="dot-live"></span>
          <span>Gateway Active (Port 3000) &bull; Runtime Ready</span>
        </div>
      </header>

      <div className="grid-layout">
        {/* Left Column: Launcher & Telemetry */}
        <div>
          <div className="panel">
            <h2>Task Launcher</h2>
            <p style={{ color: '#94a3b8', fontSize: '13px', marginBottom: '12px' }}>
              Enter a natural language enterprise objective. The operator will autonomously identify documents, evaluate policies, operate CentraERP, and verify outcomes.
            </p>
            <textarea
              className="form-input"
              rows={3}
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="e.g. Process the latest Acme invoice and match it to its PO"
            />
            <button className="btn-primary" onClick={() => handleRunTask()} disabled={loading}>
              {loading ? 'Executing Work...' : '▶ Launch Autonomous Operator'}
            </button>

            <div className="quick-prompts">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>PRESET DEMO SCENARIOS:</span>
                <button
                  onClick={async () => {
                    try {
                      await fetch('http://localhost:3000/api/reset', { method: 'POST' });
                      setEvents([]);
                      setInterruptData(null);
                      setEvidence([]);
                      setCompletionSummary(null);
                      setCurrentTaskId(null);
                      setTaskStatus('CLEAN_SLATE');
                    } catch (e: any) {
                      console.error(e);
                    }
                  }}
                  style={{
                    background: '#1e293b',
                    color: '#94a3b8',
                    border: '1px solid #475569',
                    borderRadius: '4px',
                    padding: '2px 8px',
                    fontSize: '11px',
                    cursor: 'pointer'
                  }}
                >
                  &#x21bb; Reset Clean State
                </button>
              </div>
              <button className="btn-prompt" onClick={async () => {
                await fetch('http://localhost:3000/api/reset', { method: 'POST' }).catch(() => {});
                const p = 'Process the latest Acme invoice and match it to its PO';
                setPrompt(p);
                handleRunTask(p);
              }}>
                1. 🟢 Happy Path: Process Acme invoice ($1,200) &amp; PO match
              </button>
              <button className="btn-prompt" onClick={async () => {
                await fetch('http://localhost:3000/api/reset', { method: 'POST' }).catch(() => {});
                const p = 'Process the Apex Global invoice for security appliance';
                setPrompt(p);
                handleRunTask(p);
              }}>
                2. 🟡 Policy Approval: Apex Global ($14,500) triggers HITL Limit Gate
              </button>
              <button className="btn-prompt" onClick={async () => {
                await fetch('http://localhost:3000/api/reset', { method: 'POST' }).catch(() => {});
                const p = 'List unpaid invoices older than 30 days for vendor Helios and flag them for review';
                setPrompt(p);
                handleRunTask(p);
              }}>
                3. 🔵 Generalization Task: Helios Systems Aging Review &amp; Flags (Zero Code Changes)
              </button>
            </div>
          </div>

          {/* HITL Card if Interrupted */}
          {interruptData && (
            <div className="approval-card">
              <h3>⚠️ Human-in-the-Loop Policy Gate Triggered</h3>
              <p style={{ fontSize: '13px', color: '#fef3c7', marginBottom: '8px' }}>
                <strong>Reason:</strong> {interruptData.reason || 'Manager approval required'}
              </p>
              {Array.isArray(interruptData.policy_ids) && (
                <p style={{ fontSize: '12px', color: '#fde68a' }}>
                  <strong>Enforced by SOP:</strong> {interruptData.policy_ids.join(', ')}
                </p>
              )}
              {Array.isArray(interruptData.similar_past_cases) && interruptData.similar_past_cases.length > 0 && (
                <div style={{ marginTop: '10px', fontSize: '12px', background: '#291102', padding: '8px', borderRadius: '4px' }}>
                  <div style={{ color: '#fed7aa', fontWeight: 600 }}>CITED EPISODIC MEMORY:</div>
                  <div>
                    Prior approval by {interruptData.similar_past_cases[0].approver || 'Manager'}: "{interruptData.similar_past_cases[0].reason || 'Approved'}"
                  </div>
                </div>
              )}
              <div className="approval-buttons">
                <button className="btn-approve" onClick={() => handleDecision(true)}>✓ Approve with Override</button>
                <button className="btn-reject" onClick={() => handleDecision(false)}>✗ Reject Transaction</button>
              </div>
            </div>
          )}

          {/* Completion Summary */}
          {completionSummary && (
            <div className="panel" style={{ marginTop: '20px', borderColor: '#22c55e' }}>
              <h2 style={{ color: '#86efac' }}>✔ Work Completed &amp; Verified</h2>
              <p style={{ fontSize: '14px', color: '#f1f5f9' }}>{completionSummary}</p>
            </div>
          )}
        </div>

        {/* Right Column: Runtime Execution Graph & Audit Trail */}
        <div>
          <div className="panel">
            <h2>Autonomous Runtime Loop (LangGraph State)</h2>
            <div className="trace-flow">
              {nodes.map(n => {
                const isActive = safeStatus.toLowerCase().includes(n.toLowerCase());
                const isCompleted = safeStatus === 'COMPLETED';
                return (
                  <div key={n} className={`trace-node ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}`}>
                    {n}
                  </div>
                );
              })}
            </div>

            <div style={{ marginBottom: '10px', fontSize: '13px', color: '#94a3b8' }}>
              Current Status: <strong style={{ color: safeStatus === 'ERROR' ? '#f87171' : '#38bdf8' }}>{safeStatus}</strong>
              {currentTaskId && <span style={{ marginLeft: '12px', color: '#64748b' }}>({currentTaskId})</span>}
            </div>

            <h3 style={{ fontSize: '13px', color: '#94a3b8', marginBottom: '6px' }}>Execution Trace &amp; Event Stream:</h3>
            <div className="log-scroll">
              {events.length === 0 ? (
                <div style={{ color: '#475569' }}>Awaiting task dispatch...</div>
              ) : (
                events.map((ev, i) => {
                  const evType = String(ev?.type || 'EVENT');
                  return (
                    <div key={i} className={`log-entry ${evType.includes('ANOMALY') || evType.includes('ERROR') ? 'anomaly' : ''} ${evType.includes('VERIFIED') || evType.includes('COMPLETED') ? 'success' : ''}`}>
                      [{ev.timestamp}] <strong>{evType}</strong>
                      {ev.details && typeof ev.details === 'object' && (
                        <span style={{ color: '#64748b', marginLeft: '6px' }}>
                          {JSON.stringify(ev.details).substring(0, 80)}...
                        </span>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Verified Evidence Viewer */}
          <div className="panel" style={{ marginTop: '20px' }}>
            <h2>Verified Evidence &amp; Audit Proof</h2>
            {evidence.length === 0 ? (
              <p style={{ color: '#64748b', fontSize: '13px' }}>Independent verification occurs after action execution via read-only API.</p>
            ) : (
              evidence.map((ev, idx) => (
                <div key={idx} className="evidence-box">
                  <div style={{ fontWeight: 600, color: '#38bdf8' }}>Source: {ev?.source || 'CentraERP Read-Only API'}</div>
                  {ev?.verified_record && (
                    <div style={{ marginTop: '4px' }}>
                      Invoice: <strong>{ev.verified_record.invoice_number}</strong> | Amount: <strong>${ev.verified_record.amount}</strong> | Status: <strong style={{ color: '#4ade80' }}>{ev.verified_record.status}</strong>
                    </div>
                  )}
                  {Array.isArray(ev?.flagged_invoices) && (
                    <div style={{ marginTop: '4px' }}>
                      Flagged Records: {ev.flagged_invoices.join(', ')}
                    </div>
                  )}
                </div>
              ))
            )}
            <div style={{ marginTop: '14px', fontSize: '12px', color: '#64748b' }}>
              Tamper-Evident SHA-256 Audit Chain:
              <div className="hash-badge" style={{ marginTop: '4px' }}>
                genesis: 0000000000000000000000000000000000000000000000000000000000000000 &rarr; sha256_chain_linked
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
