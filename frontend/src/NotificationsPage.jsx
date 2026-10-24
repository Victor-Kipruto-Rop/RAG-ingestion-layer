import React, { useCallback, useEffect, useState } from 'react';
import { Activity, AlertTriangle, BellRing, CheckCircle2, Clock3, RefreshCw, ShieldAlert } from 'lucide-react';
import { api } from './api.js';

const dateLabel = value => {
  if (!value) return 'Time not provided';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
};
const status = job => String(job.status || 'unknown').toLowerCase();
const titleFor = job => {
  const value = status(job);
  if (['failed', 'error', 'dead_letter', 'dead-letter'].includes(value)) return 'Ingestion requires attention';
  if (['queued', 'pending'].includes(value)) return 'Ingestion job queued';
  if (['processing', 'running', 'in_progress'].includes(value)) return 'Ingestion job in progress';
  if (['completed_with_errors'].includes(value)) return 'Ingestion completed with row errors';
  return 'Ingestion job completed';
};

export default function NotificationsPage({ onViewJobs }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [updatedAt, setUpdatedAt] = useState(null);
  const refresh = useCallback(async () => {
    setBusy(true); setError('');
    try {
      const response = await api('/api/v1/admin/ingestion/jobs?page=1&page_size=100');
      const result = await response.json();
      const jobs = (result.items || []).filter(job => ['failed','error','dead_letter','dead-letter','queued','pending','processing','running','in_progress','completed_with_errors'].includes(status(job)));
      setItems(jobs.map(job => ({
        id: job.id || job.job_id,
        title: titleFor(job),
        detail: job.error_summary || job.file_name || 'The backend returned a job status without additional detail.',
        status: status(job),
        time: job.updated_at || job.completed_at || job.created_at,
        severity: ['failed','error','dead_letter','dead-letter'].includes(status(job)) ? 'critical' : 'info',
      })));
      setUpdatedAt(new Date());
    } catch (e) {
      setError(e.message || 'Could not load notifications from the backend.');
    } finally { setBusy(false); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const attention = items.filter(item => item.severity === 'critical').length;
  return <div className="notifications-page">
    <div className="page-heading"><div><div className="eyebrow-label">WORKSPACE ACTIVITY</div><h1>Notifications</h1><p>Operational alerts derived from persisted ingestion jobs. This view does not fabricate events.</p></div><button className="button-secondary" onClick={refresh} disabled={busy}><RefreshCw size={15} className={busy ? 'spin' : ''}/> Refresh</button></div>
    {error && <div className="alert-banner error"><AlertTriangle size={16}/><span>{error}</span></div>}
    <div className="metric-grid notifications-metrics">
      <article className="metric-card"><div className="metric-top"><span>Active notifications</span><span className="metric-icon mint"><BellRing size={18}/></span></div><div className="metric-value">{items.length.toLocaleString()}</div><div className="metric-note"><span>From recent persisted jobs</span></div></article>
      <article className="metric-card"><div className="metric-top"><span>Requires attention</span><span className="metric-icon amber"><ShieldAlert size={18}/></span></div><div className="metric-value">{attention.toLocaleString()}</div><div className="metric-note"><span>Failed or dead-letter jobs</span></div></article>
      <article className="metric-card"><div className="metric-top"><span>Last refreshed</span><span className="metric-icon green"><Clock3 size={18}/></span></div><div className="metric-value notifications-time">{updatedAt ? updatedAt.toLocaleTimeString() : '—'}</div><div className="metric-note"><span>{busy ? 'Refreshing from API…' : 'Backend-backed snapshot'}</span></div></article>
    </div>
    <section className="panel full-panel"><div className="panel-heading"><div><h2>Recent operational alerts</h2><p>Latest 100 jobs returned by the API; this view is not an email or push-delivery log.</p></div><span className="record-count">{items.length} alerts</span></div>
      {busy && !updatedAt ? <div className="module-empty"><Activity size={22}/><strong>Loading alerts</strong></div> : items.length ? <div className="notification-list">{items.map(item => <article className="notification-row" key={item.id}><span className={item.severity === 'critical' ? 'notification-state critical' : 'notification-state'}>{item.severity === 'critical' ? <AlertTriangle size={17}/> : <Activity size={17}/>}</span><div className="notification-copy"><strong>{item.title}</strong><span>{item.detail}</span><small>{dateLabel(item.time)} · Job {String(item.id || '').slice(0, 12)} · {item.status.replaceAll('_',' ')}</small></div><button className="button-secondary" onClick={onViewJobs}>View jobs</button></article>)}</div> : <div className="module-empty"><CheckCircle2 size={25}/><strong>No active operational alerts</strong><span>The backend did not return queued, processing, failed, or completed-with-errors jobs in the recent page.</span></div>}
    </section>
  </div>;
}
