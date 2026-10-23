import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertCircle, AlertTriangle, ArrowDownRight, ArrowRight, ArrowUpRight, ClipboardCheck,
  Bell, Building2, CheckCircle2, ChevronDown, CircleDot, Clock3, Database,
  FileCheck2, FileSpreadsheet, FileText, HardDrive, LayoutDashboard, Menu,
  MoreHorizontal, RefreshCw, Search, Server, Settings, ShieldCheck, SlidersHorizontal,
  Upload, X, ScrollText, Workflow, KeyRound, Copy, RotateCw, Trash2, LockKeyhole
} from 'lucide-react';
import { api } from './api.js';

const NAV = [
  { name: 'Overview', icon: LayoutDashboard, group: 'WORKSPACE' },
  { name: 'Data Sources', icon: Database, group: 'WORKSPACE' },
  { name: 'Ingestion Jobs', icon: Activity, group: 'WORKSPACE' },
  { name: 'Registry Records', icon: Building2, group: 'WORKSPACE' },
  { name: 'Data Quality', icon: FileCheck2, group: 'GOVERNANCE' },
  { name: 'Manual Review', icon: ClipboardCheck, group: 'GOVERNANCE' },
  { name: 'Warehouse', icon: HardDrive, group: 'GOVERNANCE' },
  { name: 'Validation Rules', icon: ShieldCheck, group: 'GOVERNANCE' },
  { name: 'Audit Logs', icon: ScrollText, group: 'ADMINISTRATION' },
  { name: 'API Keys', icon: KeyRound, group: 'ADMINISTRATION' },
  { name: 'Settings', icon: Settings, group: 'ADMINISTRATION' },
];

const dateLabel = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};
const number = (value) => Number(value || 0).toLocaleString();
const statusTone = (value) => {
  const status = String(value || '').toLowerCase();
  if (['completed', 'completed_with_errors', 'healthy', 'connected', 'ready'].includes(status)) return 'success';
  if (['processing', 'running', 'in_progress', 'pending', 'queued', 'pending_submission'].includes(status)) return 'warning';
  if (['failed', 'error', 'rejected', 'verification_failed'].includes(status)) return 'danger';
  return 'neutral';
};

function StatusPill({ value }) {
  const tone = statusTone(value);
  return <span className={`status-pill ${tone}`}><i />{String(value || 'Unknown').replaceAll('_', ' ')}</span>;
}

function Sidebar({ page, setPage, mobile, setMobile }) {
  let group = '';
  return <aside className={`sidebar ${mobile ? 'sidebar-open' : ''}`}>
    <div className="brand-row">
      <div className="brand-mark"><Database size={19} strokeWidth={2.2} /></div>
      <div className="brand-copy"><strong>PesaGuard</strong><span>DATASOURCE</span></div>
      <button className="icon-button mobile-close" onClick={() => setMobile(false)} aria-label="Close menu"><X size={18} /></button>
    </div>
    <div className="workspace-chip"><span className="pulse-dot" />INTERNAL DATA PLATFORM</div>
    <nav className="side-nav">
      {NAV.map((item) => {
        const showGroup = item.group !== group;
        group = item.group;
        return <React.Fragment key={item.name}>
          {showGroup && <div className="nav-group-label">{item.group}</div>}
          <button className={`nav-item ${page === item.name ? 'active' : ''}`} onClick={() => { setPage(item.name); setMobile(false); }}>
            <item.icon size={18} strokeWidth={1.8} /><span>{item.name}</span>
            {item.name === 'Ingestion Jobs' && <span className="nav-count">Live</span>}
          </button>
        </React.Fragment>;
      })}
    </nav>
    <div className="sidebar-footer">
      <div className="secure-icon"><ShieldCheck size={17} /></div>
      <div><strong>Secure workspace</strong><span>Operator access</span></div>
      <span className="footer-online" title="API connection status" />
    </div>
  </aside>;
}

function Topbar({ page, connected, onRefresh, loading, search, setSearch, setMobile }) {
  return <header className="topbar">
    <div className="topbar-left">
      <button className="icon-button mobile-menu" onClick={() => setMobile(true)} aria-label="Open menu"><Menu size={20} /></button>
      <div className="breadcrumb"><span>Datasource</span><span className="breadcrumb-slash">/</span><strong>{page}</strong></div>
    </div>
    <div className="topbar-tools">
      <label className="global-search"><Search size={16} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search records, jobs, sources…" /><kbd>⌘ K</kbd></label>
      <div className="environment"><span className={connected ? 'pulse-dot' : 'pulse-dot muted'} />{connected ? 'API connected' : 'Preview'}<ChevronDown size={14} /></div>
      <button className="icon-button notification-button" aria-label="Notifications"><Bell size={18} /><i /></button>
      <button className="profile-chip" aria-label="Account menu"><span>VK</span><ChevronDown size={14} /></button>
      <button className="icon-button refresh-button" onClick={onRefresh} aria-label="Refresh data" disabled={loading}><RefreshCw size={17} className={loading ? 'spin' : ''} /></button>
    </div>
  </header>;
}

function MetricCard({ icon: Icon, label, value, note, accent = 'green' }) {
  return <article className="metric-card">
    <div className="metric-top"><span>{label}</span><span className={`metric-icon ${accent}`}><Icon size={18} strokeWidth={1.8} /></span></div>
    <div className="metric-value">{value}</div>
    <div className="metric-note"><span>{note}</span></div>
  </article>;
}

function ActivityChart({ jobs }) {
  const points = useMemo(() => {
    const days = new Map();
    for (const job of jobs) {
      if (!job.created_at) continue;
      const date = new Date(job.created_at);
      if (Number.isNaN(date.getTime())) continue;
      const key = date.toISOString().slice(0, 10);
      const row = days.get(key) || { key, label: date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }), processed: 0, inserted: 0, jobs: 0 };
      row.processed += Number(job.records_processed || 0);
      row.inserted += Number(job.records_inserted || 0);
      row.jobs += 1;
      days.set(key, row);
    }
    return [...days.values()].sort((a, b) => a.key.localeCompare(b.key)).slice(-7);
  }, [jobs]);
  const max = Math.max(1, ...points.flatMap(p => [p.processed, p.inserted]));
  const chartPoints = (field) => points.map((p, i) => {
    const x = points.length <= 1 ? 50 : 28 + i * (244 / (points.length - 1));
    const y = 150 - (p[field] / max) * 112;
    return `${x},${y}`;
  }).join(' ');
  return <div className="chart-area">
    {points.length ? <>
      <div className="chart-legend"><span><i className="legend-green" />Records processed</span><span><i className="legend-mint" />Records inserted</span><span className="chart-note">Based on loaded jobs</span></div>
      <svg className="activity-chart" viewBox="0 0 300 190" role="img" aria-label="Records processed and inserted by job creation date" preserveAspectRatio="none">
        {[38, 76, 114, 152].map(y => <line key={y} x1="28" x2="274" y1={y} y2={y} className="chart-grid" />)}
        <polyline points={chartPoints('processed')} className="chart-line chart-line-dark" />
        <polyline points={chartPoints('inserted')} className="chart-line chart-line-mint" />
        {points.map((p, i) => {
          const x = points.length <= 1 ? 50 : 28 + i * (244 / (points.length - 1));
          return <g key={p.key}><circle cx={x} cy={150 - (p.processed / max) * 112} r="3.5" className="chart-point-dark" /><circle cx={x} cy={150 - (p.inserted / max) * 112} r="3.5" className="chart-point-mint" /></g>;
        })}
      </svg>
      <div className="chart-xlabels">{points.map(p => <span key={p.key}>{p.label}</span>)}</div>
    </> : <div className="chart-empty"><Activity size={25} /><strong>Activity will appear here</strong><span>Connect the API and process ingestion jobs to populate this chart.</span></div>}
  </div>;
}

function QualityPanel({ summary }) {
  const valid = summary?.data_quality?.valid_percentage;
  const missing = summary?.data_quality?.missing_percentage;
  const duplicate = summary?.data_quality?.duplicate_percentage;
  const hasQuality = [valid, missing, duplicate].some(v => v !== undefined && v !== null);
  const rows = hasQuality ? [
    ['Valid records', Number(valid || 0), 'quality-valid'],
    ['Missing required fields', Number(missing || 0), 'quality-missing'],
    ['Duplicate candidates', Number(duplicate || 0), 'quality-duplicate'],
  ] : null;
  return <div className="quality-panel">
    <div className="card-heading"><div><h2>Data quality</h2><p>Registry validation overview</p></div><div className="heading-icon"><SlidersHorizontal size={17} /></div></div>
    {rows ? rows.map(([label, pct, cls]) => <div className="quality-row" key={label}><div className="quality-label"><span>{label}</span><strong>{pct.toFixed(1)}%</strong></div><div className="quality-track"><span className={cls} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} /></div></div>) : <div className="quality-unavailable"><ShieldCheck size={24} /><strong>Quality metrics not available yet</strong><span>The API does not currently expose aggregate quality percentages. Values are intentionally not estimated.</span></div>}
    <div className="quality-foot"><span className="tiny-dot" />{hasQuality ? 'Metrics returned by API' : 'Waiting for quality metrics endpoint'}</div>
  </div>;
}

function JobsTable({ jobs, compact = false, search = '' }) {
  const filtered = jobs.filter(j => [j.file_name, j.status, j.source_name, j.id].some(v => String(v || '').toLowerCase().includes(search.toLowerCase())));
  if (!filtered.length) return <div className="empty-state"><div className="empty-icon"><Database size={23} /></div><strong>{search ? 'No matching ingestion jobs' : 'No ingestion jobs yet'}</strong><span>{search ? 'Try a different search term.' : 'Upload a dataset to create your first ingestion job.'}</span></div>;
  return <div className="table-scroll"><table className="data-table"><thead><tr><th>DATASET / FILE</th><th>STATUS</th><th>PROCESSED</th><th>INSERTED</th><th>CREATED</th><th /></tr></thead><tbody>
    {filtered.slice(0, compact ? 5 : 50).map(job => <tr key={job.id}>
      <td><div className="file-cell"><span className={`file-icon ${String(job.file_name || '').toLowerCase().endsWith('.pdf') ? 'pdf' : 'csv'}`}>{String(job.file_name || '').toLowerCase().endsWith('.pdf') ? <FileText size={17} /> : <FileSpreadsheet size={17} />}</span><span><strong>{job.file_name || 'Unnamed dataset'}</strong><small>JOB-{String(job.id || '').slice(0, 8).toUpperCase()}</small></span></div></td>
      <td><StatusPill value={job.status} /></td><td>{number(job.records_processed)}</td><td>{number(job.records_inserted)}</td><td className="date-cell">{dateLabel(job.created_at)}</td><td><button className="row-action" title="Job actions" aria-label="Job actions"><MoreHorizontal size={18} /></button></td>
    </tr>)}
  </tbody></table></div>;
}

function OrganizationsTable({ rows, total, page, pageSize, onPageChange }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (!rows.length) return <div className="empty-state"><div className="empty-icon"><Building2 size={23} /></div><strong>No registry records found</strong><span>Connect the API or import a dataset to populate the registry.</span></div>;
  return <>
    <div className="table-scroll"><table className="data-table"><thead><tr><th>ORGANIZATION</th><th>REGISTRATION NUMBER</th><th>STATUS</th><th>SOURCE FILE</th></tr></thead><tbody>{rows.map(org => <tr key={org.id}><td><div className="org-cell"><span className="org-avatar"><Building2 size={16} /></span><span><strong>{org.legal_name || 'Unnamed organization'}</strong><small>Record {String(org.id || '').slice(0, 8)}</small></span></div></td><td>{org.registration_number || '—'}</td><td><StatusPill value={org.status} /></td><td>{org.source_file || '—'}</td></tr>)}</tbody></table></div>
    <div className="pagination"><span>Showing {total ? ((page - 1) * pageSize + 1) : 0}–{Math.min(page * pageSize, total)} of {number(total)} organizations</span><div><button className="button-secondary" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>Previous</button><button className="button-secondary" disabled={page >= pages} onClick={() => onPageChange(page + 1)}>Next</button></div></div>
  </>;
}

function ServiceStatus({ label, detail, icon: Icon, value, connected }) {
  return <div className="service-card"><div className="service-icon"><Icon size={19} /></div><div className="service-copy"><strong>{label}</strong><span>{detail}</span></div><StatusPill value={value || (connected ? 'Connected' : 'Unknown')} /></div>;
}

function DataQualityPage({ request }) {
  const [summary, setSummary] = useState(null);
  const [rules, setRules] = useState([]);
  const [query, setQuery] = useState('');
  const [candidates, setCandidates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const load = async () => {
    setLoading(true); setError('');
    try {
      const [summaryResponse, rulesResponse] = await Promise.all([request('/api/v1/quality/summary'), request('/api/v1/quality/rules')]);
      const summaryBody = await summaryResponse.json(); const rulesBody = await rulesResponse.json();
      setSummary(summaryBody); setRules(rulesBody.items || []);
    } catch (e) { setError(typeof e.message === 'string' ? e.message : 'Unable to load data quality metrics.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [request]);
  const searchMatches = async (event) => {
    event.preventDefault(); if (query.trim().length < 2) return;
    setLoading(true); setError('');
    try { const response = await request(`/api/v1/registry/match-candidates?q=${encodeURIComponent(query.trim())}&limit=10`); const body = await response.json(); setCandidates(body.items || []); }
    catch (e) { setError(typeof e.message === 'string' ? e.message : 'Unable to find review candidates.'); }
    finally { setLoading(false); }
  };
  const metrics = summary || {};
  return <div className="governance-workspace">
    <div className="page-heading"><div><div className="eyebrow-label">DATA GOVERNANCE</div><h1>Data quality</h1><p>Inspect completeness, freshness and review signals calculated from persisted records.</p></div><button className="button-secondary" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''}/> Refresh metrics</button></div>
    {error && <div className="alert-banner error"><AlertTriangle size={16}/><span>{error}</span></div>}
    <div className="metric-grid quality-metric-grid">
      <MetricCard icon={Building2} label="Total records" value={summary ? number(metrics.total_records) : '—'} note="Persisted organizations"/>
      <MetricCard icon={AlertCircle} label="Missing registration" value={summary ? number(metrics.missing_registration_number) : '—'} note="Needs context-aware review" accent="amber"/>
      <MetricCard icon={FileCheck2} label="Missing tax PIN" value={summary ? number(metrics.missing_tax_pin) : '—'} note="Missing data, not a failure" accent="mint"/>
      <MetricCard icon={Clock3} label="Stale candidates" value={summary ? number(metrics.stale_records) : '—'} note={`Not seen for ${metrics.stale_after_days || 180}+ days`} accent="amber"/>
    </div>
    <section className="panel"><div className="panel-heading"><div><h2>Active quality checks</h2><p>Checks and reporting rules currently implemented by the service.</p></div><span className="record-count">{rules.length} checks</span></div>
      <div className="quality-rules-list">{rules.map(rule => <article className="quality-rule-row" key={rule.id}><span className={`rule-severity ${String(rule.severity).toLowerCase()}`}>{rule.severity}</span><div><strong>{rule.name}</strong><p>{rule.description}</p><small>{rule.enforced_at}</small></div><StatusPill value={rule.status}/></article>)}</div>
    </section>
    <section className="panel"><div className="panel-heading"><div><h2>Potential entity matches</h2><p>Search for similar legal names to support manual review. Similarity does not verify identity.</p></div></div>
      <form className="match-search-form" onSubmit={searchMatches}><input value={query} onChange={e => setQuery(e.target.value)} minLength={2} maxLength={200} placeholder="Enter a legal name to compare" /><button className="button-primary" disabled={loading || query.trim().length < 2}><Search size={15}/> Find candidates</button></form>
      {candidates.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>ORGANIZATION</th><th>REGISTRATION</th><th>SOURCE</th><th>SIMILARITY</th><th>REVIEW</th></tr></thead><tbody>{candidates.map(row => <tr key={row.organization_id}><td><strong>{row.legal_name}</strong></td><td>{row.registration_number || '—'}</td><td>{row.source_name || 'Unknown'}</td><td>{row.score}%</td><td><StatusPill value={row.review_status}/></td></tr>)}</tbody></table></div> : <div className="keys-empty"><Search size={20}/><strong>No candidates to show</strong><span>Search for a name. Results are suggestions only and are never merged automatically.</span></div>}
    </section>
    {summary && <p className="governance-footnote">Calculated {dateLabel(summary.generated_at)}. These indicators are data-quality signals, not legal verification, fraud findings or compliance decisions.</p>}
  </div>;
}

function DataSourcesPage({ request }) {
  const [sources, setSources] = useState([]);
  const [freshness, setFreshness] = useState([]);
  const [name, setName] = useState('');
  const [sourceKey, setSourceKey] = useState('');
  const [sourceType, setSourceType] = useState('IMPORTED_DATASET');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const load = async () => {
    setLoading(true); setError('');
    try {
      const [sourcesResponse, freshnessResponse] = await Promise.all([request('/api/v1/sources'), request('/api/v1/sources/freshness')]);
      const sourceBody = await sourcesResponse.json(); const freshnessBody = await freshnessResponse.json();
      setSources(sourceBody.items || []); setFreshness(freshnessBody.items || []);
    } catch (e) { setError(typeof e.message === 'string' ? e.message : 'Unable to load data sources.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [request]);
  const addSource = async (event) => {
    event.preventDefault(); setLoading(true); setError(''); setMessage('');
    try {
      await request('/api/v1/sources', { method: 'POST', body: JSON.stringify({ source_key: sourceKey.trim().toLowerCase(), display_name: name.trim(), source_type: sourceType, jurisdiction: 'KE', enabled: true, precedence: 100 }) });
      setName(''); setSourceKey(''); setMessage('Source registered. It is metadata only until an authorized dataset is imported.'); await load();
    } catch (e) { setError(typeof e.message === 'string' ? e.message : 'Could not register source. The key may need sources:write permission.'); }
    finally { setLoading(false); }
  };
  const freshnessByKey = new Map(freshness.map(item => [item.source_key, item]));
  return <div className="governance-workspace">
    <div className="page-heading"><div><div className="eyebrow-label">SOURCE GOVERNANCE</div><h1>Data sources</h1><p>Manage source metadata and inspect freshness state without overstating external connectivity.</p></div><button className="button-secondary" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''}/> Refresh</button></div>
    {error && <div className="alert-banner error"><AlertTriangle size={16}/><span>{error}</span></div>}
    {message && <div className="alert-banner success"><CheckCircle2 size={16}/><span>{message}</span></div>}
    <section className="panel"><div className="panel-heading"><div><h2>Register source metadata</h2><p>Register only a source you are authorized to use. This does not create a provider connection.</p></div></div>
      <form className="source-create-form" onSubmit={addSource}><label>Display name<input value={name} onChange={e => setName(e.target.value)} required maxLength={200} placeholder="e.g. Licensed registry dataset"/></label><label>Source key<input value={sourceKey} onChange={e => setSourceKey(e.target.value.replace(/[^a-zA-Z0-9_-]/g, '').toLowerCase())} required maxLength={100} pattern="[a-zA-Z0-9_-]+" placeholder="e.g. brs-public-dataset"/></label><label>Source type<select value={sourceType} onChange={e => setSourceType(e.target.value)}><option value="IMPORTED_DATASET">Imported dataset</option><option value="GOVERNMENT_API">Government API</option><option value="COMMERCIAL_PROVIDER">Commercial provider</option><option value="MANUAL_REVIEW">Manual review</option></select></label><button className="button-primary" disabled={loading || !name.trim() || !sourceKey.trim()}>Register metadata</button></form>
    </section>
    <section className="panel"><div className="panel-heading"><div><h2>Registered sources</h2><p>{sources.length} source metadata records returned by the API.</p></div></div>
      {!sources.length ? <div className="keys-empty"><Database size={22}/><strong>No sources registered</strong><span>Register source metadata above or import a dataset with a configured source key.</span></div> : <div className="table-scroll"><table className="data-table"><thead><tr><th>SOURCE</th><th>KEY</th><th>TYPE</th><th>JURISDICTION</th><th>FRESHNESS</th><th>STATUS</th></tr></thead><tbody>{sources.map(source => <tr key={source.id}><td><strong>{source.display_name}</strong><small>{source.licence_reference || 'No licence reference recorded'}</small></td><td>{source.source_key}</td><td>{source.source_type}</td><td>{source.jurisdiction}</td><td>{freshnessByKey.get(source.source_key)?.freshness_status || 'unknown'}</td><td><StatusPill value={source.enabled ? 'enabled' : 'disabled'}/></td></tr>)}</tbody></table></div>}
    </section>
  </div>;
}

export function AuditLogsPage({ request }) {
  const [items, setItems] = useState([]);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const pageSize = 50;
  const load = async (nextOffset = offset) => {
    setLoading(true); setError('');
    try {
      const response = await request(`/api/v1/audit/logs?limit=${pageSize}&offset=${nextOffset}`);
      const body = await response.json(); setItems(body.items || []); setTotal(Number(body.total || 0)); setOffset(nextOffset);
    } catch(e) { setError(typeof e.message === 'string' ? e.message : 'Unable to load audit logs.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(0); }, [request]);
  return <div className="governance-workspace"><div className="page-heading"><div><div className="eyebrow-label">AUDIT & ACCOUNTABILITY</div><h1>Audit logs</h1><p>Inspect persisted ingestion and operator events. Sensitive raw credentials are not displayed.</p></div><button className="button-secondary" onClick={() => load(offset)} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''}/> Refresh</button></div>
    {error && <div className="alert-banner error" role="alert"><AlertTriangle size={16}/><span>{error}</span></div>}
    <section className="panel"><div className="panel-heading"><div><h2>Audit events</h2><p>Showing {total ? offset + 1 : 0}–{Math.min(offset + items.length, total)} of {number(total)} events.</p></div><span className="record-count">{number(total)} events</span></div>
      {!items.length && !loading ? <div className="keys-empty"><ScrollText size={22}/><strong>No audit events found</strong><span>Events appear when imports or operator key-management actions are recorded.</span></div> : <div className="table-scroll"><table className="data-table audit-table"><thead><tr><th>EVENT</th><th>ACTOR</th><th>FILE</th><th>DETAILS</th><th>TIME</th></tr></thead><tbody>{items.map(item => <tr key={item.id}><td><strong>{item.action}</strong></td><td>{item.actor}</td><td>{item.file_name || '—'}</td><td><code>{JSON.stringify(item.details || {}).slice(0,180)}</code></td><td>{dateLabel(item.created_at)}</td></tr>)}</tbody></table></div>}
      <div className="table-pagination"><span>Page {Math.floor(offset / pageSize) + 1} of {Math.max(1, Math.ceil(total / pageSize))}</span><div><button className="button-secondary" onClick={() => load(Math.max(0, offset - pageSize))} disabled={loading || offset === 0}>Previous</button><button className="button-secondary" onClick={() => load(offset + pageSize)} disabled={loading || offset + items.length >= total || items.length === 0}>Next</button></div></div>
    </section>
  </div>;
}

function ValidationRulesPage({ request }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState('');
  useEffect(() => { request('/api/v1/quality/rules').then(r => r.json()).then(body => setItems(body.items || [])).catch(e => setError(typeof e.message === 'string' ? e.message : 'Unable to load rules.')); }, [request]);
  return <div className="governance-workspace"><div className="page-heading"><div><div className="eyebrow-label">DATA GOVERNANCE</div><h1>Validation rules</h1><p>Current checks exposed by the backend; rule editing is not enabled yet.</p></div></div>
    {error && <div className="alert-banner error"><AlertTriangle size={16}/><span>{error}</span></div>}
    <section className="panel"><div className="panel-heading"><div><h2>Implemented checks</h2><p>Rules are shown with their actual enforcement point.</p></div></div><div className="quality-rules-list">{items.map(rule => <article className="quality-rule-row" key={rule.id}><span className={`rule-severity ${String(rule.severity).toLowerCase()}`}>{rule.severity}</span><div><strong>{rule.name}</strong><p>{rule.description}</p><small>{rule.enforced_at}</small></div><StatusPill value={rule.status}/></article>)}</div></section>
  </div>;
}

export function APIKeysPage() {
  const [token, setToken] = useState('');
  const [items, setItems] = useState([]);
  const [events, setEvents] = useState([]);
  const [name, setName] = useState('Datasource integration');
  const [environment, setEnvironment] = useState('sandbox');
  const [scopes, setScopes] = useState(['registry:read']);
  const [expires, setExpires] = useState('90');
  const [secret, setSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const headers = () => ({ Authorization: `Bearer ${token}` });
  const load = async () => {
    if (!token.trim()) { setError('Enter the operator token configured on the server.'); return; }
    setLoading(true); setError('');
    try {
      const [keysResponse, eventsResponse] = await Promise.all([
        api('/api/v1/admin/api-keys', { headers: headers() }),
        api('/api/v1/admin/security-events?limit=100', { headers: headers() })
      ]);
      const keys = await keysResponse.json(); const audit = await eventsResponse.json();
      setItems(keys.items || []); setEvents(audit.items || []); setMessage('Operator access verified.');
    } catch (e) { setError(typeof e.message === 'string' ? e.message : 'Could not load key management. Check the token and server configuration.'); }
    finally { setLoading(false); }
  };
  const create = async (event) => {
    event.preventDefault(); setLoading(true); setError(''); setSecret(''); setMessage('');
    try {
      const response = await api('/api/v1/admin/api-keys', { method: 'POST', headers: headers(), body: JSON.stringify({ name, environment, scopes, expires_in_days: expires ? Number(expires) : null }) });
      const result = await response.json(); setSecret(result.secret || ''); setMessage(result.warning || 'Key created. Copy it now.'); await load();
    } catch (e) { setError(typeof e.message === 'string' ? e.message : 'Could not create API key.'); }
    finally { setLoading(false); }
  };
  const revoke = async (item) => {
    if (!window.confirm(`Revoke ${item.key_prefix}? Applications using this key will stop working.`)) return;
    setLoading(true); setError('');
    try { await api(`/api/v1/admin/api-keys/${item.id}`, { method: 'DELETE', headers: headers() }); setSecret(''); setMessage('API key revoked.'); await load(); }
    catch (e) { setError(typeof e.message === 'string' ? e.message : 'Could not revoke key.'); }
    finally { setLoading(false); }
  };
  const rotate = async (item) => {
    if (!window.confirm(`Rotate ${item.key_prefix}? The existing key will be revoked immediately.`)) return;
    setLoading(true); setError(''); setSecret('');
    try {
      const response = await api(`/api/v1/admin/api-keys/${item.id}/rotate`, { method: 'POST', headers: headers(), body: JSON.stringify({ expires_in_days: expires ? Number(expires) : null }) });
      const result = await response.json(); setSecret(result.secret || ''); setMessage(result.warning || 'Key rotated. Copy the new secret now.'); await load();
    } catch (e) { setError(typeof e.message === 'string' ? e.message : 'Could not rotate key.'); }
    finally { setLoading(false); }
  };
  const copySecret = async () => {
    try { await navigator.clipboard.writeText(secret); setMessage('Secret copied. Store it in your secret manager; it will not be shown again.'); }
    catch { setMessage('Clipboard access was blocked. Select and copy the secret manually, then store it securely.'); }
  };
  const toggleScope = (scope) => setScopes(current => current.includes(scope) ? current.filter(s => s !== scope) : [...current, scope]);
  return <div className="keys-workspace">
    <div className="page-heading"><div><div className="eyebrow-label">SECURITY & ACCESS</div><h1>API keys</h1><p>Create isolated credentials for sandbox and production integrations.</p></div><div className="heading-actions"><span className="keys-security-chip"><LockKeyhole size={14}/> Secret shown once</span></div></div>
    <section className="panel keys-admin-panel">
      <div className="panel-heading"><div><h2>Operator access</h2><p>Enter the server-side DATASOURCE_ADMIN_TOKEN. It is held in this page's memory only and is not saved to local storage.</p></div></div>
      <form className="keys-token-form" onSubmit={e => { e.preventDefault(); load(); }}>
        <input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} placeholder="Operator bearer token" aria-label="Operator bearer token"/>
        <button className="button-primary" disabled={loading || !token.trim()}>{loading ? 'Checking…' : 'Unlock key management'}</button>
      </form>
      {error && <div className="keys-inline-error"><AlertTriangle size={15}/>{error}</div>}
      {message && <div className="keys-inline-success"><CheckCircle2 size={15}/>{message}</div>}
    </section>
    {secret && <section className="panel secret-reveal">
      <div className="secret-reveal-icon"><KeyRound size={19}/></div><div className="secret-reveal-copy"><strong>Copy your new API key now</strong><p>This is the only time the full secret is displayed. Do not commit it or place it in frontend source code.</p>
        <input readOnly value={secret} onFocus={e => e.target.select()} aria-label="New API key secret"/>
      </div><button className="button-primary" onClick={copySecret}><Copy size={15}/> Copy secret</button>
    </section>}
    <section className="panel">
      <div className="panel-heading"><div><h2>Create API key</h2><p>Choose an environment and the minimum permissions the integration needs.</p></div></div>
      <form className="keys-create-form" onSubmit={create}>
        <label>Key name<input value={name} onChange={e => setName(e.target.value)} minLength={2} maxLength={120} required placeholder="e.g. Reconciliation service"/></label>
        <label>Environment<select value={environment} onChange={e => setEnvironment(e.target.value)}><option value="sandbox">Sandbox · testing only</option><option value="production">Production · live requests</option></select></label>
        <label>Expiry<select value={expires} onChange={e => setExpires(e.target.value)}><option value="30">30 days</option><option value="90">90 days</option><option value="180">180 days</option><option value="365">365 days</option><option value="">No expiry</option></select></label>
        <div className="keys-scope-field"><span>Permissions</span><div className="keys-scopes">
          {['registry:read','ingestion:write','sources:write','exports:read','reviews:write'].map(scope => <label key={scope}><input type="checkbox" checked={scopes.includes(scope)} onChange={() => toggleScope(scope)}/><span>{scope}</span></label>)}
        </div></div>
        <div className="keys-environment-warning"><ShieldCheck size={17}/><span><strong>Environment lock</strong> — sandbox credentials are rejected by production deployments, return API_KEY_ENVIRONMENT_MISMATCH, and generate a security event. The server deployment's DATASOURCE_ENVIRONMENT determines the target; a client header cannot override it.</span></div>
        <button className="button-primary" disabled={loading || !token.trim() || scopes.length === 0}><KeyRound size={16}/> Generate {environment === 'sandbox' ? 'sandbox' : 'production'} key</button>
      </form>
    </section>
    <section className="panel">
      <div className="panel-heading"><div><h2>Managed keys</h2><p>Only prefixes are shown after creation. Full secrets are never retrievable.</p></div><button className="button-secondary" onClick={load} disabled={loading || !token.trim()}><RefreshCw size={14} className={loading ? 'spin' : ''}/> Refresh</button></div>
      {!items.length ? <div className="keys-empty"><KeyRound size={22}/><strong>No managed keys loaded</strong><span>Unlock key management and refresh to view existing credentials.</span></div> :
        <div className="table-scroll"><table className="data-table keys-table"><thead><tr><th>KEY</th><th>ENVIRONMENT</th><th>PERMISSIONS</th><th>LAST USED</th><th>EXPIRES</th><th>STATUS</th><th>ACTIONS</th></tr></thead><tbody>
          {items.map(item => <tr key={item.id}><td><strong>{item.name}</strong><small className="key-prefix">{item.key_prefix}</small></td><td><span className={`env-pill ${item.environment}`}>{item.environment}</span></td><td><span className="keys-scope-summary">{(item.scopes || []).join(', ')}</span></td><td>{item.last_used_at ? dateLabel(item.last_used_at) : 'Never'}</td><td>{item.expires_at ? dateLabel(item.expires_at) : 'No expiry'}</td><td><StatusPill value={item.status}/></td><td><div className="keys-row-actions"><button className="row-action" title="Rotate key" aria-label="Rotate key" disabled={loading || item.status !== 'active'} onClick={() => rotate(item)}><RotateCw size={15}/></button><button className="row-action" title="Revoke key" aria-label="Revoke key" disabled={loading || item.status !== 'active'} onClick={() => revoke(item)}><Trash2 size={15}/></button></div></td></tr>)}
        </tbody></table></div>}
    </section>
    <section className="panel">
      <div className="panel-heading"><div><h2>Security events</h2><p>Recent managed-key misuse and permission-denial events.</p></div></div>
      {!events.length ? <div className="keys-empty"><ShieldCheck size={22}/><strong>No security events loaded</strong><span>Events appear when managed keys are used incorrectly or denied.</span></div> :
        <div className="table-scroll"><table className="data-table keys-table"><thead><tr><th>EVENT</th><th>KEY PREFIX</th><th>KEY ENVIRONMENT</th><th>REQUEST ENVIRONMENT</th><th>ENDPOINT</th><th>TIME</th></tr></thead><tbody>{events.map(event => <tr key={event.id}><td><StatusPill value={event.event_type}/></td><td>{event.key_prefix || 'Unknown key'}</td><td>{event.key_environment || 'Unknown'}</td><td>{event.expected_environment || 'Unknown'}</td><td>{event.http_method} {event.endpoint}</td><td>{dateLabel(event.created_at)}</td></tr>)}</tbody></table></div>}
    </section>
  </div>;
}

export function ManualReviewPage({ request }) {
  const [items, setItems] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const load = async () => {
    setLoading(true); setError('');
    try {
      const response = await request('/api/v1/reviews/queue?limit=100');
      const body = await response.json();
      setItems(body.items || []);
      setDrafts(current => {
        const next = { ...current };
        for (const item of (body.items || [])) {
          if (!next[item.organization_id]) next[item.organization_id] = { decision: 'needs_more_evidence', reason: '' };
        }
        return next;
      });
    } catch (e) { setError(typeof e.message === 'string' ? e.message : 'Unable to load the review queue.'); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [request]);
  const updateDraft = (id, field, value) => setDrafts(current => ({
    ...current,
    [id]: { ...(current[id] || { decision: 'needs_more_evidence', reason: '' }), [field]: value },
  }));
  const submit = async (event, item) => {
    event.preventDefault();
    const draft = drafts[item.organization_id] || {};
    if ((draft.reason || '').trim().length < 5) {
      setError('Enter a review reason of at least 5 characters.');
      return;
    }
    setSavingId(item.organization_id); setError(''); setMessage('');
    try {
      const response = await request(`/api/v1/reviews/${item.organization_id}/decisions`, {
        method: 'POST',
        body: JSON.stringify({ decision: draft.decision, reason: draft.reason.trim() }),
      });
      await response.json();
      setMessage(`Review decision saved for ${item.legal_name}.`);
      setDrafts(current => ({ ...current, [item.organization_id]: { ...current[item.organization_id], reason: '' } }));
      await load();
    } catch (e) { setError(typeof e.message === 'string' ? e.message : 'Unable to save this review decision.'); }
    finally { setSavingId(''); }
  };
  return <div className="governance-workspace">
    <div className="page-heading"><div><div className="eyebrow-label">DATA GOVERNANCE</div><h1>Manual review</h1><p>Record and audit reviewer decisions without changing canonical registry data or automatically merging organizations.</p></div><button className="button-secondary" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'spin' : ''}/> Refresh queue</button></div>
    {error && <div className="alert-banner error" role="alert"><AlertTriangle size={16}/><span>{error}</span></div>}
    {message && <div className="alert-banner" role="status"><CheckCircle2 size={16}/><span>{message}</span></div>}
    <section className="panel">
      <div className="panel-heading"><div><h2>Review queue</h2><p>{items.length} record(s) loaded. Records needing more evidence or reopened decisions remain in the queue.</p></div><span className="record-count">{number(items.length)} records</span></div>
      {!items.length && !loading ? <div className="keys-empty"><ClipboardCheck size={22}/><strong>No records awaiting review</strong><span>Unreviewed records will appear here when available.</span></div> : <div className="table-scroll"><table className="data-table review-table"><thead><tr><th>ORGANIZATION</th><th>REGISTRATION</th><th>SOURCE</th><th>QUALITY</th><th>DECISION</th><th>REVIEW REASON</th><th>ACTION</th></tr></thead><tbody>
        {items.map(item => {
          const draft = drafts[item.organization_id] || { decision: 'needs_more_evidence', reason: '' };
          return <tr key={item.organization_id}>
            <td><strong>{item.legal_name}</strong><small>{item.organization_id}</small></td>
            <td>{item.registration_number || 'Not provided'}</td><td>{item.source_name || 'Unknown source'}</td><td><StatusPill value={item.data_quality_status}/></td>
            <td><select aria-label={`Decision for ${item.legal_name}`} value={draft.decision} onChange={e => updateDraft(item.organization_id, 'decision', e.target.value)}>
              <option value="possible_duplicate">Possible duplicate</option><option value="not_duplicate">Not a duplicate</option><option value="needs_more_evidence">Need more evidence</option><option value="record_incorrect">Record appears incorrect</option><option value="reopened">Reopen review</option>
            </select></td>
            <td><input aria-label={`Reason for ${item.legal_name}`} value={draft.reason} onChange={e => updateDraft(item.organization_id, 'reason', e.target.value)} placeholder="Explain the evidence reviewed" maxLength={2000}/></td>
            <td><button className="button-primary" disabled={savingId === item.organization_id || loading} onClick={e => submit(e, item)}>{savingId === item.organization_id ? 'Saving…' : 'Save decision'}</button></td>
          </tr>;
        })}
      </tbody></table></div>}
      <p className="small-print">Review decisions are internal assessments only. They are not proof of fraud, legal non-compliance, or authoritative verification from BRS/KRA/IPRS.</p>
    </section>
  </div>;
}

export default function App() {
  const [page, setPage] = useState('Overview');
  const [key, setKey] = useState('');
  const [connected, setConnected] = useState(false);
  const [summary, setSummary] = useState(null);
  const [orgs, setOrgs] = useState([]);
  const [orgPage, setOrgPage] = useState(1);
  const [orgTotal, setOrgTotal] = useState(0);
  const [jobs, setJobs] = useState([]);
  const [search, setSearch] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [mobile, setMobile] = useState(false);

  const request = useCallback((path, opts = {}) => api(path, { ...opts, headers: { ...(opts.headers || {}), 'X-API-Key': key } }), [key]);
  const refresh = useCallback(async () => {
    if (!key) return;
    setLoading(true); setError('');
    try {
      const [metricsResponse, orgResponse, jobsResponse] = await Promise.all([
        request('/api/v1/metrics/summary'),
        request(`/api/v1/organizations?page=${orgPage}&page_size=100${search ? `&q=${encodeURIComponent(search)}` : ''}`),
        request('/api/v1/ingestion/jobs?page_size=50')
      ]);
      const metrics = await metricsResponse.json();
      const orgResult = await orgResponse.json();
      const jobsResult = await jobsResponse.json();
      setSummary(metrics); setOrgs(orgResult.items || []); setOrgTotal(orgResult.total || 0);
      setJobs(jobsResult.items || []); setConnected(true);
    } catch (e) { setConnected(false); setError(e.message || 'Unable to connect to the Registry API.'); }
    finally { setLoading(false); }
  }, [key, request, orgPage, search]);

  useEffect(() => { if (key) refresh(); }, [key, refresh]);
  const upload = async (event) => {
    event.preventDefault();
    if (!file) return;
    setLoading(true); setError(''); setMessage('Uploading file and creating an ingestion job…');
    try {
      let result;
      if (file.size > 50 * 1024 * 1024) {
        const presignResponse = await request('/api/v1/ingestion/uploads/presign', { method: 'POST', body: JSON.stringify({ file_name: file.name, size_bytes: file.size }) });
        const ticket = await presignResponse.json();
        setMessage('Uploading directly to private object storage…');
        const putStatus = await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest(); xhr.open('PUT', ticket.upload_url); xhr.setRequestHeader('Content-Type', ticket.content_type);
          xhr.upload.onprogress = (e) => { if (e.lengthComputable) setMessage(`Uploading directly to private object storage… ${Math.round(e.loaded / e.total * 100)}%`); };
          xhr.onload = () => resolve(xhr.status); xhr.onerror = () => reject(new Error('Direct storage upload failed. Check bucket CORS and retry before the upload URL expires.')); xhr.send(file);
        });
        if (putStatus < 200 || putStatus >= 300) throw new Error('Direct storage upload failed. Check bucket CORS and retry before the upload URL expires.');
        const completeResponse = await request(`/api/v1/ingestion/uploads/${ticket.job_id}/complete`, { method: 'POST' });
        result = await completeResponse.json();
      } else {
        const form = new FormData(); form.append('file', file);
        const response = await request('/api/v1/ingestion/uploads', { method: 'POST', body: form });
        result = await response.json();
      }
      setMessage(`Queued job ${String(result.job_id || '').slice(0, 8)}. Processing runs asynchronously; refresh the jobs list for the outcome.`);
      setFile(null); await refresh();
    } catch (e) { setMessage(''); setError(e.message || 'Upload failed.'); }
    finally { setLoading(false); }
  };

  const metrics = summary || {};
  const navToUpload = () => setPage('Upload center');
  const knownPage = ['Overview', 'Data Sources', 'Ingestion Jobs', 'Registry Records', 'Data Quality', 'Manual Review', 'Warehouse', 'Validation Rules', 'Audit Logs', 'Settings', 'API Keys', 'Upload center'].includes(page);

  return <div className="app-shell">
    {mobile && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMobile(false)} />}
    <Sidebar page={page} setPage={setPage} mobile={mobile} setMobile={setMobile} />
    <main className="main-content">
      <Topbar page={page} connected={connected} onRefresh={refresh} loading={loading} search={search} setSearch={setSearch} setMobile={setMobile} />
      <div className="page-content">
        {!connected && page !== 'API Keys' && <section className="connect-banner"><div className="connect-banner-icon"><ShieldCheck size={20} /></div><div className="connect-copy"><strong>Connect your datasource</strong><p>Enter the internal API key to load live registry metrics and ingestion jobs. Avoid production service keys in browser-based previews.</p></div><form onSubmit={e => { e.preventDefault(); refresh(); }}><input type="password" value={key} onChange={e => setKey(e.target.value)} placeholder="Internal API key" autoComplete="off" /><button className="button-primary">Connect <ArrowRight size={15} /></button></form></section>}
        {error && <div className="alert-banner error"><AlertTriangle size={17} /><span>{error}</span><button onClick={() => setError('')} aria-label="Dismiss error"><X size={16} /></button></div>}
        {message && <div className="alert-banner success"><CheckCircle2 size={17} /><span>{message}</span><button onClick={() => setMessage('')} aria-label="Dismiss message"><X size={16} /></button></div>}

        {page === 'Overview' && <>
          <div className="page-heading"><div><div className="eyebrow-label">REGISTRY OPERATIONS</div><h1>Datasource overview</h1><p>Monitor registry ingestion, data quality, and warehouse activity from one workspace.</p></div><div className="heading-actions"><button className="button-secondary" onClick={() => setPage('Ingestion Jobs')}>View jobs</button><button className="button-primary" onClick={navToUpload}><Upload size={16} /> Upload dataset</button></div></div>
          <div className="metric-grid">
            <MetricCard icon={Building2} label="Indexed organizations" value={summary ? number(metrics.total_organizations) : '—'} note="Persisted registry records" />
            <MetricCard icon={Workflow} label="Ingestion jobs" value={summary ? number(metrics.total_jobs) : '—'} note="Tracked import runs" accent="mint" />
            <MetricCard icon={CheckCircle2} label="Completed jobs" value={summary ? number(metrics.completed_jobs) : '—'} note="Successfully processed" accent="green" />
            <MetricCard icon={AlertCircle} label="Failed jobs" value={summary ? number(metrics.failed_jobs) : '—'} note="May require investigation" accent="amber" />
          </div>
          <div className="dashboard-grid">
            <section className="panel activity-panel"><div className="panel-heading"><div><h2>Ingestion activity</h2><p>Processed and inserted records from recent jobs</p></div><span className="panel-period"><Activity size={14} /> Recent activity</span></div><ActivityChart jobs={jobs} /></section>
            <section className="panel"><QualityPanel summary={summary} /></section>
          </div>
          <section className="panel jobs-panel"><div className="panel-heading"><div><h2>Recent ingestion jobs</h2><p>Latest persisted pipeline activity</p></div><button className="button-link" onClick={() => setPage('Ingestion Jobs')}>View all jobs <ArrowRight size={15} /></button></div><JobsTable jobs={jobs} compact search={search} /></section>
          <section className="infra-section"><div className="section-title"><div><h2>Infrastructure health</h2><p>Connection state reported by the current datasource session</p></div><span className="health-summary"><i /> {connected ? 'API reachable' : 'Awaiting connection'}</span></div><div className="service-grid"><ServiceStatus label="Registry API" detail="Datasource application" value={connected ? 'Connected' : 'Not connected'} connected={connected} icon={Server} /><ServiceStatus label="Database metrics" detail="Registry data access" value={summary ? 'Available' : 'Unknown'} connected={!!summary} icon={Database} /><ServiceStatus label="External verification" detail="KRA / BRS integrations" value="Not configured" connected={false} icon={ShieldCheck} /></div></section>
        </>}

        {page === 'Ingestion Jobs' && <section className="panel full-panel"><div className="panel-heading"><div><h2>Ingestion jobs</h2><p>Inspect persisted import outcomes and processing counts.</p></div><button className="button-secondary" onClick={refresh} disabled={loading}><RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh</button></div><JobsTable jobs={jobs} search={search} /></section>}
        {page === 'Registry Records' && <section className="panel full-panel"><div className="panel-heading"><div><h2>Registry records</h2><p>Search imported organizations and inspect source information.</p></div><span className="record-count">{number(orgTotal)} records</span></div><OrganizationsTable rows={orgs} total={orgTotal} page={orgPage} pageSize={100} onPageChange={setOrgPage} /></section>}
        {page === 'API Keys' && <APIKeysPage />}
        {page === 'Data Sources' && <DataSourcesPage request={request} />}
        {page === 'Data Quality' && <DataQualityPage request={request} />}
        {page === 'Manual Review' && <ManualReviewPage request={request} />}
        {page === 'Validation Rules' && <ValidationRulesPage request={request} />}
        {page === 'Audit Logs' && <AuditLogsPage request={request} />}
        {page === 'Warehouse' && <section className="panel full-panel"><div className="panel-heading"><div><h2>Warehouse records</h2><p>Browse the canonical organization records currently exposed by the registry API.</p></div><span className="record-count">{number(orgTotal)} records</span></div><OrganizationsTable rows={orgs} total={orgTotal} page={orgPage} pageSize={100} onPageChange={setOrgPage} /></section>}
        {page === 'Settings' && <section className="panel full-panel"><div className="panel-heading"><div><h2>Datasource settings</h2><p>Runtime connection and integration settings.</p></div></div><div className="settings-list"><div><strong>Datasource API</strong><span>{connected ? 'Connected' : 'Not connected'}</span></div><div><strong>Environment</strong><span>Determined by the server deployment; clients cannot switch it with a request header.</span></div><div><strong>Managed key administration</strong><span>Configured separately with DATASOURCE_ADMIN_TOKEN. Keep it private and never embed it in frontend source.</span></div><div><strong>External registry providers</strong><span>Not configured by this dashboard. BRS/KRA provider access requires approved credentials and integration tests.</span></div></div></section>}
        {page === 'Upload center' && <section className="panel upload-panel"><div className="panel-heading"><div><h2>Upload dataset</h2><p>Submit registry files for asynchronous ingestion.</p></div><div className="heading-icon"><Upload size={18} /></div></div><form onSubmit={upload} className="upload-form"><label className="dropzone"><input type="file" accept=".csv,.pdf" onChange={e => setFile(e.target.files?.[0] || null)} /><span className="dropzone-icon"><Upload size={25} /></span><strong>{file ? file.name : 'Choose a dataset to upload'}</strong><span>{file ? `${(file.size / 1048576).toFixed(2)} MB · ready to submit` : 'Drag a file here or browse from your device'}</span><small>CSV and PDF · backend size limits apply</small></label><div className="upload-actions"><p>Only upload datasets you are authorized to process. PDF files may be stored even where structured extraction is not yet enabled.</p><button className="button-primary" disabled={!file || loading}>{loading ? 'Submitting…' : <><Upload size={16} /> Queue import</>}</button></div></form></section>}
        {!knownPage && <section className="coming-soon panel"><div className="coming-icon"><Database size={25} /></div><span className="eyebrow-label">DATASOURCE MODULE</span><h2>{page}</h2><p>This navigation entry is reserved for the {page.toLowerCase()} workspace. Its production data view has not been connected yet, so this screen does not display fabricated records.</p><button className="button-secondary" onClick={() => setPage('Overview')}>Return to overview</button></section>}
        <footer className="page-footer"><span>© PesaGuard Datasource</span><span><span className={connected ? 'footer-status-dot' : 'footer-status-dot muted'} />{connected ? 'Connected to datasource API' : 'Local preview · not connected'}</span></footer>
      </div>
    </main>
  </div>;
}
