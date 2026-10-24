import React, { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, BellRing, CheckCircle2, Clock3, RefreshCw, ShieldAlert, Check } from 'lucide-react';
import { api } from './api.js';

const dateLabel = value => {
  if (!value) return 'Time not provided';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
};

export default function NotificationsPage({ onViewJobs }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [marking, setMarking] = useState(false);
  const [error, setError] = useState('');
  const [updatedAt, setUpdatedAt] = useState(null);
  const refresh = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const response = await api('/api/v1/admin/notifications');
      const result = await response.json();
      setItems(result.items || []);
      setUpdatedAt(new Date());
    } catch (e) { setError(e.message || 'Could not load notifications from the backend. Apply the database migration and retry.'); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const markRead = async keys => {
    if (!keys.length) return;
    setMarking(true); setError('');
    try {
      await api('/api/v1/admin/notifications/read', { method: 'POST', body: JSON.stringify({ notification_keys: keys }) });
      await refresh();
    } catch (e) { setError(e.message || 'Could not update notification read state.'); }
    finally { setMarking(false); }
  };
  const unread = items.filter(item => !item.read).length;
  const attention = items.filter(item => item.severity === 'critical' && !item.read).length;
  return <div className="notifications-page">
    <div className="page-heading"><div><div className="eyebrow-label">WORKSPACE ACTIVITY</div><h1>Notifications</h1><p>Operational alerts derived from persisted ingestion jobs, with read state stored by the backend.</p></div><div className="heading-actions"><button className="button-secondary" onClick={refresh} disabled={busy}><RefreshCw size={15} className={busy ? 'spin' : ''}/> Refresh</button><button className="button-primary" onClick={() => markRead(items.filter(item => !item.read).map(item => item.id))} disabled={marking || unread === 0}><Check size={15}/>{marking ? 'Saving…' : 'Mark all read'}</button></div></div>
    {error && <div className="alert-banner error"><AlertTriangle size={16}/><span>{error}</span></div>}
    <div className="metric-grid notifications-metrics">
      <article className="metric-card"><div className="metric-top"><span>Unread notifications</span><span className="metric-icon mint"><BellRing size={18}/></span></div><div className="metric-value">{unread.toLocaleString()}</div><div className="metric-note"><span>Persisted read-state tracking</span></div></article>
      <article className="metric-card"><div className="metric-top"><span>Requires attention</span><span className="metric-icon amber"><ShieldAlert size={18}/></span></div><div className="metric-value">{attention.toLocaleString()}</div><div className="metric-note"><span>Unread failed or dead-letter jobs</span></div></article>
      <article className="metric-card"><div className="metric-top"><span>Last refreshed</span><span className="metric-icon green"><Clock3 size={18}/></span></div><div className="metric-value notifications-time">{updatedAt ? updatedAt.toLocaleTimeString() : '—'}</div><div className="metric-note"><span>{busy ? 'Refreshing from API…' : 'Backend-backed snapshot'}</span></div></article>
    </div>
    <section className="panel full-panel"><div className="panel-heading"><div><h2>Recent operational alerts</h2><p>Latest 100 ingestion jobs; this is not an email or push-delivery log.</p></div><span className="record-count">{items.length} alerts</span></div>
      {busy && !updatedAt ? <div className="module-empty"><Activity size={22}/><strong>Loading alerts</strong></div> : items.length ? <div className="notification-list">{items.map(item => <article className={item.read ? 'notification-row is-read' : 'notification-row'} key={item.id}><span className={item.severity === 'critical' ? 'notification-state critical' : 'notification-state'}>{item.severity === 'critical' ? <AlertTriangle size={17}/> : <Activity size={17}/>}</span><div className="notification-copy"><strong>{item.title}</strong><span>{item.detail}</span><small>{dateLabel(item.created_at)} · {item.status.replaceAll('_',' ')} · {item.read ? 'Read' : 'Unread'}</small></div><div className="notification-actions">{!item.read && <button className="button-secondary" disabled={marking} onClick={() => markRead([item.id])}><Check size={14}/> Mark read</button>}<button className="button-link" onClick={onViewJobs}>View jobs</button></div></article>)}</div> : <div className="module-empty"><CheckCircle2 size={25}/><strong>No operational alerts</strong><span>The backend did not return queued, processing, failed, or completed-with-errors jobs in the recent page.</span></div>}
    </section>
  </div>;
}
