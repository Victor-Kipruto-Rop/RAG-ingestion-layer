import React, { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Clock3, Laptop, LogOut, RefreshCw, ShieldCheck, Smartphone, Trash2 } from 'lucide-react';
import { api } from './api.js';

const when = value => { if (!value) return 'Unknown'; const d = new Date(value); return Number.isNaN(d.getTime()) ? 'Unknown' : d.toLocaleString(); };
function deviceLabel(agent) {
  const value = String(agent || '').toLowerCase();
  const device = /android|iphone|ipad|mobile/.test(value) ? 'Mobile device' : 'Desktop / browser';
  const browser = /edg\//.test(value) ? 'Edge' : /firefox\//.test(value) ? 'Firefox' : /chrome\//.test(value) ? 'Chrome' : /safari\//.test(value) ? 'Safari' : 'Browser';
  return { device, browser, icon: device === 'Mobile device' ? Smartphone : Laptop };
}

export default function SessionManagementPage({ onCurrentSessionRevoked }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(true);
  const [revoking, setRevoking] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const refresh = useCallback(async () => {
    setBusy(true); setError('');
    try { const r = await api('/api/v1/admin/sessions'); const data = await r.json(); setItems(data.items || []); }
    catch (e) { setError(e.message || 'Unable to load persisted sessions. Ensure database migrations are applied.'); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const revoke = async item => {
    const label = item.current ? 'this current session' : 'this session';
    if (!window.confirm('Revoke ' + label + '? The session will no longer be able to access the workspace.')) return;
    setRevoking(item.id); setError(''); setMessage('');
    try {
      const r = await api('/api/v1/admin/sessions/' + encodeURIComponent(item.id), { method: 'DELETE' });
      const result = await r.json();
      if (result.current_session) { onCurrentSessionRevoked(); return; }
      setItems(current => current.filter(row => row.id !== item.id));
      setMessage('Session revoked. Its cookie/token is no longer accepted by the backend.');
    } catch (e) { setError(e.message || 'Could not revoke the selected session.'); }
    finally { setRevoking(''); }
  };
  const others = items.filter(x => !x.current).length;
  return <div className="sessions-page">
    <div className="page-heading"><div><div className="eyebrow-label">ACCOUNT SECURITY</div><h1>Session management</h1><p>Review active operator sessions and revoke access for devices you no longer use.</p></div><button className="button-secondary" onClick={refresh} disabled={busy}><RefreshCw size={15} className={busy ? 'spin' : ''}/> Refresh sessions</button></div>
    {error && <div className="alert-banner error"><AlertTriangle size={16}/><span>{error}</span></div>}
    {message && <div className="alert-banner success"><ShieldCheck size={16}/><span>{message}</span></div>}
    <div className="metric-grid sessions-metrics"><article className="metric-card"><div className="metric-top"><span>Active sessions</span><span className="metric-icon green"><ShieldCheck size={18}/></span></div><div className="metric-value">{items.length}</div><div className="metric-note"><span>Read from the session database</span></div></article><article className="metric-card"><div className="metric-top"><span>Other devices</span><span className="metric-icon mint"><Laptop size={18}/></span></div><div className="metric-value">{others}</div><div className="metric-note"><span>Sessions besides this browser</span></div></article><article className="metric-card"><div className="metric-top"><span>Session policy</span><span className="metric-icon amber"><Clock3 size={18}/></span></div><div className="metric-value sessions-policy">Sliding expiry</div><div className="metric-note"><span>Revocation checked on each authenticated request</span></div></article></div>
    <section className="panel sessions-list"><div className="panel-heading"><div><h2>Signed-in devices</h2><p>Session identifiers are not exposed. Device information is based on the browser user-agent string.</p></div></div>
      {busy ? <div className="module-empty"><RefreshCw size={20} className="spin"/><strong>Loading sessions</strong></div> : !items.length ? <div className="module-empty"><ShieldCheck size={24}/><strong>No active sessions found</strong><span>Refresh after signing in again if this looks unexpected.</span></div> : <div className="session-items">{items.map(item => { const d = deviceLabel(item.user_agent); const Icon = d.icon; return <article className="session-item" key={item.id}><span className="session-device-icon"><Icon size={20}/></span><div className="session-device-copy"><div className="session-title-row"><strong>{d.browser} · {d.device}</strong>{item.current && <span className="session-current-badge">THIS DEVICE</span>}</div><p>{item.user_agent || 'Unknown browser/device'}</p><div className="session-times"><span>Last active: {when(item.last_seen_at)}</span><span>Signed in: {when(item.created_at)}</span><span>Expires: {when(item.expires_at)}</span></div><small>Method: {String(item.auth_method || 'unknown').replaceAll('_',' ')}</small></div><button className={item.current ? 'button-secondary session-revoke-current' : 'button-danger session-revoke'} onClick={() => revoke(item)} disabled={!!revoking} title={item.current ? 'Revoke current session and sign out' : 'Revoke session'}>{revoking === item.id ? <RefreshCw size={15} className="spin"/> : item.current ? <LogOut size={15}/> : <Trash2 size={15}/>}<span>{item.current ? 'Sign out' : 'Revoke'}</span></button></article>; })}</div>}
    </section>
    <div className="alert-banner info sessions-tip"><ShieldCheck size={16}/><span>If you suspect unauthorized access, revoke unfamiliar sessions and reset your password. Password reset revokes all sessions for that account.</span></div>
  </div>;
}
