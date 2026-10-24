import React, { useCallback, useEffect, useState } from 'react';
import { api } from './api.js';
import { AlertTriangle, Check, ClipboardCheck, RefreshCw, ShieldCheck, XCircle } from 'lucide-react';

async function requestJson(path, options = {}) {
  const response = await api(path, options);
  const body = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail || body?.message || `Request failed (${response.status})`);
  return body;
}

export default function DeveloperAccessReviewPage() {
  const [items, setItems] = useState([]);
  const [evidence, setEvidence] = useState({});
  const [notes, setNotes] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const refresh = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const result = await requestJson('/api/v1/admin/developer/production-access/requests');
      setItems(result.items || []);
    } catch (e) { setError(e.message || 'Could not load developer access requests.'); }
    finally { setBusy(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const verifyWorkspace = async item => {
    const evidenceReference = (evidence[item.workspace_id] || '').trim();
    if (evidenceReference.length < 8) {
      setError('Enter an evidence reference (at least 8 characters) before verifying this workspace.');
      return;
    }
    setBusy(true); setError(''); setNotice('');
    try {
      await requestJson(`/api/v1/admin/developer/workspaces/${encodeURIComponent(item.workspace_id)}/verification`, {
        method: 'POST',
        body: JSON.stringify({ verified: true, evidence_reference: evidenceReference,
          reviewer_note: (notes[item.id] || '').trim() || 'Workspace verification reviewed by an operator.' }),
      });
      setNotice(`Workspace ${item.workspace_name || item.workspace_id} marked verified. Production access still requires separate approval.`);
      await refresh();
    } catch (e) { setError(e.message || 'Workspace verification failed.'); }
    finally { setBusy(false); }
  };

  const review = async (item, status) => {
    const reviewerNote = (notes[item.id] || '').trim();
    if (reviewerNote.length < 5) {
      setError('Add a review note of at least 5 characters before approving or rejecting.');
      return;
    }
    if (status === 'approved' && !item.workspace_verified) {
      setError('Verify the workspace with authoritative evidence before approving production access.');
      return;
    }
    setBusy(true); setError(''); setNotice('');
    try {
      await requestJson(`/api/v1/admin/developer/production-access/requests/${encodeURIComponent(item.id)}/review`, {
        method: 'POST', body: JSON.stringify({ status, reviewer_note: reviewerNote }),
      });
      setNotice(`Production access request ${status}.`);
      await refresh();
    } catch (e) { setError(e.message || 'Review could not be saved.'); }
    finally { setBusy(false); }
  };

  return <div className="panel full-panel">
    <div className="panel-heading">
      <div><h2>Developer access review</h2><p>Review live API access requests. Workspace verification and production access approval are separate decisions.</p></div>
      <button className="button-secondary" onClick={refresh} disabled={busy}><RefreshCw size={15}/> Refresh</button>
    </div>
    {error && <div className="inline-error" role="alert"><AlertTriangle size={16}/>{error}</div>}
    {notice && <div className="inline-success" role="status"><Check size={16}/>{notice}</div>}
    {items.length === 0 ? <div className="empty-state"><ShieldCheck size={24}/><strong>No production access requests</strong><p>Submitted requests will appear here for review.</p></div> :
      <div className="developer-access-list">{items.map(item => <section className="developer-access-card" key={item.id}>
        <div className="developer-access-head"><div><h3>{item.workspace_name || 'Developer workspace'}</h3><p>{item.id} · {new Date(item.created_at).toLocaleString()}</p></div><span className={`status-pill ${item.status === 'approved' ? 'success' : item.status === 'rejected' ? 'danger' : 'warning'}`}>{item.status}</span></div>
        <div className="developer-access-meta"><span>Workspace verified: <strong>{item.workspace_verified ? 'Yes' : 'No'}</strong></span><span>Production access: <strong>{item.production_access_approved ? 'Approved' : 'Not approved'}</strong></span><span>Expected volume: <strong>{item.expected_volume}</strong></span></div>
        <p className="developer-access-usecase">{item.use_case}</p>
        {item.reviewer_note && <p className="developer-access-note">Previous review: {item.reviewer_note}</p>}
        {!item.workspace_verified && <div className="developer-access-verify"><label>Authoritative evidence reference<input value={evidence[item.workspace_id] || ''} onChange={e => setEvidence(v => ({...v, [item.workspace_id]: e.target.value}))} minLength={8} maxLength={1000} placeholder="Verification case ID or evidence reference"/></label><button className="button-secondary" disabled={busy} onClick={() => verifyWorkspace(item)}><ClipboardCheck size={15}/> Verify workspace</button></div>}
        {item.status === 'pending' && <div className="developer-access-review"><label>Reviewer note<input value={notes[item.id] || ''} onChange={e => setNotes(v => ({...v, [item.id]: e.target.value}))} minLength={5} maxLength={1000} placeholder="Document your decision"/></label><div><button className="button-primary" disabled={busy || !item.workspace_verified} onClick={() => review(item, 'approved')}><Check size={15}/> Approve production</button><button className="button-danger" disabled={busy} onClick={() => review(item, 'rejected')}><XCircle size={15}/> Reject</button></div></div>}
      </section>)}</div>}
  </div>;
}
