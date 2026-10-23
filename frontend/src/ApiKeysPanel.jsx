import React, { useCallback, useState } from 'react';
import { api } from './api.js';
import { AlertTriangle, Check, Copy, KeyRound, Plus, RefreshCw, ShieldCheck, Trash2, Eye, EyeOff } from 'lucide-react';

const dateLabel = value => value ? new Date(value).toLocaleString() : 'Never';
async function request(path, token, options = {}) {
  const response = await api(path, { ...options, headers: { ...(options.headers || {}), Authorization: `Bearer ${token}` } });
  return response.status === 204 ? null : response.json();
}
function friendlyError(error) {
  if (typeof error?.message === 'string') return error.message;
  return 'Request failed. Check the access token and API connection.';
}

export default function ApiKeysPanel() {
  const [token, setToken] = useState('');
  const [connected, setConnected] = useState(false);
  const [items, setItems] = useState([]);
  const [events, setEvents] = useState([]);
  const [name, setName] = useState('My integration');
  const [environment, setEnvironment] = useState('sandbox');
  const [expires, setExpires] = useState('90');
  const [scopes, setScopes] = useState(['registry:read']);
  const [secret, setSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const refresh = useCallback(async () => {
    if (!token.trim()) { setConnected(false); return; }
    setBusy(true); setError('');
    try {
      const [keyResult, auditResult] = await Promise.all([
        request('/api/v1/keys', token),
        request('/api/v1/keys/audit/events?limit=50', token),
      ]);
      setItems(keyResult.items || []); setEvents(auditResult.items || []);
      setConnected(true);
    } catch (e) { setConnected(false); setError(friendlyError(e)); }
    finally { setBusy(false); }
  }, [token]);

  const create = async (e) => {
    e.preventDefault(); setBusy(true); setError(''); setMessage(''); setSecret('');
    try {
      const result = await request('/api/v1/keys', token, { method: 'POST', body: JSON.stringify({
        name, environment, expires_in_days: expires ? Number(expires) : null, scopes
      }) });
      setSecret(result.secret); setShowSecret(true);
      setMessage(`${environment === 'sandbox' ? 'Sandbox' : 'Production'} key created. Copy the secret now; it cannot be retrieved again.`);
      await refresh();
    } catch (e) { setError(friendlyError(e)); }
    finally { setBusy(false); }
  };
  const rotate = async (item) => {
    if (!window.confirm(`Rotate “${item.name}”? The existing key will be revoked immediately.`)) return;
    setBusy(true); setError(''); setSecret('');
    try { const result = await request(`/api/v1/keys/${item.id}/rotate`, token, { method: 'POST' }); setSecret(result.secret); setShowSecret(true); setMessage('Key rotated. Copy the new secret now. The previous key has been revoked.'); await refresh(); }
    catch (e) { setError(friendlyError(e)); } finally { setBusy(false); }
  };
  const revoke = async (item) => {
    if (!window.confirm(`Revoke “${item.name}”? Requests using this key will stop working.`)) return;
    setBusy(true); setError('');
    try { await request(`/api/v1/keys/${item.id}`, token, { method: 'DELETE' }); setMessage('API key revoked.'); await refresh(); }
    catch (e) { setError(friendlyError(e)); } finally { setBusy(false); }
  };
  const copySecret = async () => { try { await navigator.clipboard.writeText(secret); setMessage('Secret copied to clipboard. Store it in a secret manager; do not commit it to source control.'); } catch { setError('Clipboard access failed. Select and copy the secret manually.'); } };

  return <div className="api-keys-page">
    <div className="page-heading"><div><div className="eyebrow-label">ACCESS & SECURITY</div><h1>API keys</h1><p>Create separate credentials for sandbox testing and live production integrations.</p></div><button className="button-secondary" onClick={refresh} disabled={busy || !token}><RefreshCw size={15} /> Refresh</button></div>
    <div className="key-security-note"><ShieldCheck size={20} /><div><strong>Environment isolation is enforced by the API</strong><p>Sandbox keys only work on the sandbox deployment. Production keys only work on production. Changing a dropdown or request header cannot override the server environment.</p></div></div>
    {!connected && <section className="panel key-auth-panel"><div className="panel-heading"><div><h2>Connect your PesaGuard account</h2><p>Paste a short-lived access token issued by the trusted PesaGuard identity service. This is not your datasource service API key.</p></div><KeyRound size={20} /></div><label className="key-field-label">PesaGuard user access token<input type="password" value={token} onChange={e => setToken(e.target.value)} autoComplete="off" placeholder="Bearer token (value only)" /></label><div className="key-form-actions"><button className="button-primary" onClick={refresh} disabled={!token.trim() || busy}>Connect account</button><span>Kept in memory only; re-enter after reload or when you leave this page.</span></div></section>}
    {error && <div className="alert-banner error"><AlertTriangle size={17} /><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
    {message && <div className="alert-banner success"><Check size={17} /><span>{message}</span><button onClick={() => setMessage('')} aria-label="Dismiss message">×</button></div>}
    {secret && <section className="panel generated-secret"><div className="secret-heading"><div className="heading-icon"><KeyRound size={18} /></div><div><h2>Copy your new API key</h2><p>This secret is shown only once. Store it in a secrets manager and never expose it in frontend code.</p></div></div><div className="secret-value"><code>{showSecret ? secret : '•'.repeat(36)}</code><button className="icon-button" onClick={() => setShowSecret(v => !v)} aria-label={showSecret ? 'Hide secret' : 'Show secret'}>{showSecret ? <EyeOff size={17} /> : <Eye size={17} />}</button><button className="button-secondary" onClick={copySecret}><Copy size={15} /> Copy</button></div><button className="button-link" onClick={() => { setSecret(''); setShowSecret(false); }}>I have stored the key</button></section>}
    {connected && <>
      <div className="key-layout">
        <section className="panel key-create-panel"><div className="panel-heading"><div><h2>Generate an API key</h2><p>Secrets are hashed at rest and shown once.</p></div><div className="heading-icon"><Plus size={18} /></div></div>
          <form onSubmit={create} className="key-create-form">
            <label className="key-field-label">Key name<input value={name} onChange={e => setName(e.target.value)} required minLength={2} maxLength={100} placeholder="e.g. Staging integration" /></label>
            <label className="key-field-label">Environment<select value={environment} onChange={e => setEnvironment(e.target.value)}><option value="sandbox">Sandbox — test data only</option><option value="production">Production — live integration</option></select></label>
            <label className="key-field-label">Expiry<select value={expires} onChange={e => setExpires(e.target.value)}><option value="30">30 days</option><option value="90">90 days</option><option value="180">180 days</option><option value="365">365 days</option></select></label>
            <fieldset className="scope-field"><legend>Permissions</legend>{[['registry:read','Read registry records'],['sources:read','Read data sources'],['ingestion:read','Read ingestion jobs and errors'],['ingestion:write','Submit ingestion uploads']].map(([scope,label])=><label key={scope}><input type="checkbox" checked={scopes.includes(scope)} onChange={e=>setScopes(old=>e.target.checked?[...old,scope]:old.filter(x=>x!==scope))}/><span>{label}</span></label>)}</fieldset>
            {environment === 'production' && <div className="production-warning"><AlertTriangle size={16} />Production key creation requires an owner/admin role and a verified organization.</div>}
            <button className="button-primary" disabled={busy || !name.trim() || !scopes.length}><KeyRound size={15} /> {busy ? 'Working…' : `Generate ${environment === 'sandbox' ? 'sandbox' : 'production'} key`}</button>
          </form>
        </section>
        <section className="panel key-list-panel"><div className="panel-heading"><div><h2>Your API keys</h2><p>{items.length} key record{items.length === 1 ? '' : 's'} for this organization</p></div><span className="record-count">{items.filter(x=>x.status==='active').length} active</span></div>
          {items.length ? <div className="key-table-wrap"><table className="key-table"><thead><tr><th>Name</th><th>Environment</th><th>Status</th><th>Last used</th><th>Actions</th></tr></thead><tbody>{items.map(item=><tr key={item.id}><td><strong>{item.name}</strong><code>{item.key_prefix}…</code><small>Expires: {dateLabel(item.expires_at)}</small></td><td><span className={`environment-badge ${item.environment}`}>{item.environment}</span></td><td><span className={`status-pill ${item.status==='active'?'success':'danger'}`}><i />{item.status}</span></td><td>{dateLabel(item.last_used_at)}</td><td><div className="key-actions"><button className="button-secondary" disabled={busy || item.status!=='active'} onClick={()=>rotate(item)}><RefreshCw size={13}/> Rotate</button><button className="icon-button danger-icon" title="Revoke key" aria-label={`Revoke ${item.name}`} disabled={busy || item.status!=='active'} onClick={()=>revoke(item)}><Trash2 size={15}/></button></div></td></tr>)}</tbody></table></div> : <div className="keys-empty"><KeyRound size={25}/><strong>No API keys yet</strong><span>Generate a sandbox key to start testing your integration.</span></div>}
        </section>
      </div>
      <section className="panel key-audit-panel"><div className="panel-heading"><div><h2>Security audit trail</h2><p>Key creation, rotation, revocation and environment-mismatch attempts.</p></div><ShieldCheck size={19}/></div>{events.length ? <div className="audit-list">{events.map(ev=><div className="audit-row" key={ev.id}><span className={ev.action.includes('mismatch')?'audit-alert':'audit-dot'}>{ev.action.includes('mismatch')?'!':'•'}</span><div><strong>{ev.action.replaceAll('.',' ')}</strong><small>{dateLabel(ev.created_at)} · {ev.details?.path || 'API key management'}</small>{ev.details?.key_environment && <p>Key environment: {ev.details.key_environment} · Requested environment: {ev.details.requested_environment}</p>}</div></div>)}</div> : <div className="keys-empty compact">No audit events returned yet.</div>}</section>
    </>}
    <p className="key-setup-footnote">Deployment setup is required before enabling customer access: apply migration 009, configure the trusted JWT issuer/secret/audience, and deploy an isolated sandbox API with its own database and storage. See <code>docs/environment-scoped-api-keys.md</code>.</p>
  </div>;
}
