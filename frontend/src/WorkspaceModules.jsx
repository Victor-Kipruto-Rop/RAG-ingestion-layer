import React, { useMemo, useState } from 'react';
import { Activity, ArrowRight, CheckCircle2, Clock3, Database, FileCheck2, FileText, HardDrive, Layers3, LockKeyhole, RefreshCw, Search, ShieldAlert, ShieldCheck, SlidersHorizontal, Workflow, CircleHelp } from 'lucide-react';

const n = v => Number(v || 0).toLocaleString();
const when = v => v ? new Date(v).toLocaleString() : '—';
const tone = v => ['completed','completed_with_errors','healthy','connected','ready'].includes(String(v || '').toLowerCase()) ? 'success' : ['failed','error','rejected'].includes(String(v || '').toLowerCase()) ? 'danger' : 'warning';
function Pill({value}) { return <span className={'module-pill '+tone(value)}><i/>{String(value || 'Unknown').replaceAll('_',' ')}</span>; }
function Heading({eyebrow,title,description,action}) { return <div className="page-heading"><div><div className="eyebrow-label">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>; }
function Stat({icon:Icon,label,value,detail}) { return <article className="module-stat"><span className="module-stat-icon"><Icon size={18}/></span><div><small>{label}</small><strong>{value}</strong><span>{detail}</span></div></article>; }
function Empty({icon:Icon=Database,title,detail}) { return <div className="module-empty"><span><Icon size={23}/></span><strong>{title}</strong><p>{detail}</p></div>; }

export default function WorkspaceModules({page,summary,jobs,orgs,orgTotal,connected,loading,refresh,setPage,search,setSearch}) {
  const [sourceQuery,setSourceQuery] = useState('');
  const sources = useMemo(() => {
    const map = new Map();
    jobs.forEach(job => { const name = job.source_name || job.source?.name || 'Unspecified source'; const key = String(name); const row = map.get(key) || {name:key,jobs:0,records:0,last:null}; row.jobs++; row.records += Number(job.records_processed || 0); if (!row.last || new Date(job.created_at || 0) > new Date(row.last || 0)) row.last=job.created_at; map.set(key,row); });
    return [...map.values()].filter(x=>x.name.toLowerCase().includes(sourceQuery.toLowerCase())).sort((a,b)=>b.jobs-a.jobs);
  },[jobs,sourceQuery]);
  const metrics = summary || {};
  const completed = jobs.filter(j=>['completed','completed_with_errors'].includes(String(j.status||'').toLowerCase())).length;
  const failed = jobs.filter(j=>['failed','error'].includes(String(j.status||'').toLowerCase())).length;
  if (page === 'Data Sources') return <div className="module-page">
    <Heading eyebrow="INGESTION CONFIGURATION" title="Data sources" description="Review source activity observed in persisted ingestion jobs. The list reflects returned backend data only." action={<button className="button-secondary" onClick={refresh} disabled={loading}><RefreshCw size={15}/> Refresh</button>}/>
    <div className="module-stats"><Stat icon={Layers3} label="Observed sources" value={sources.length} detail="Distinct source labels in jobs"/><Stat icon={Workflow} label="Ingestion jobs" value={n(jobs.length)} detail="Currently loaded jobs"/><Stat icon={Database} label="Records processed" value={n(jobs.reduce((a,j)=>a+Number(j.records_processed||0),0))} detail="Across loaded jobs"/></div>
    <section className="panel module-panel"><div className="panel-heading"><div><h2>Source activity</h2><p>Source labels are derived from persisted job metadata, not sample records.</p></div><label className="module-search"><Search size={15}/><input value={sourceQuery} onChange={e=>setSourceQuery(e.target.value)} placeholder="Filter sources"/></label></div>
      {sources.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>SOURCE</th><th>JOBS</th><th>RECORDS PROCESSED</th><th>LAST ACTIVITY</th></tr></thead><tbody>{sources.map(s=><tr key={s.name}><td><div className="module-name"><span><Database size={16}/></span><strong>{s.name}</strong></div></td><td>{n(s.jobs)}</td><td>{n(s.records)}</td><td>{when(s.last)}</td></tr>)}</tbody></table></div> : <Empty title={sourceQuery?'No matching sources':'No source activity yet'} detail="When a dataset is submitted, source metadata from its persisted ingestion job will appear here."/>}
    </section>
    <div className="module-note"><ShieldCheck size={17}/><div><strong>Catalogue management</strong><p>The backend source catalogue is protected by service API-key authentication. This browser page intentionally does not embed that secret; a server-side admin proxy is required for editing registered sources.</p></div></div>
    <div className="module-actions"><button className="button-primary" onClick={()=>setPage('Upload center')}>Upload a dataset <ArrowRight size={15}/></button><button className="button-secondary" onClick={()=>setPage('Ingestion Jobs')}>View ingestion jobs</button></div>
  </div>;
  if (page === 'Data Quality') return <div className="module-page">
    <Heading eyebrow="GOVERNANCE" title="Data quality" description="Quality indicators reported by the backend and persisted ingestion outcomes." action={<button className="button-secondary" onClick={refresh} disabled={loading}><RefreshCw size={15}/> Refresh</button>}/>
    <div className="module-stats"><Stat icon={CheckCircle2} label="Completed jobs" value={summary?n(metrics.completed_jobs):n(completed)} detail={summary?'Backend summary':'Derived from loaded job statuses'}/><Stat icon={ShieldAlert} label="Failed jobs" value={summary?n(metrics.failed_jobs):n(failed)} detail={summary?'Backend summary':'Derived from loaded job statuses'}/><Stat icon={Database} label="Registry records" value={summary?n(metrics.total_organizations):n(orgTotal)} detail="Persisted organizations"/></div>
    <section className="panel module-panel"><div className="panel-heading"><div><h2>Quality signal availability</h2><p>We only show quality percentages when the API supplies them.</p></div><SlidersHorizontal size={19}/></div>
      {metrics.data_quality && ['valid_percentage','missing_percentage','duplicate_percentage'].some(k=>metrics.data_quality[k]!==undefined&&metrics.data_quality[k]!==null) ? <div className="quality-metric-list">{[['Valid records','valid_percentage'],['Missing required fields','missing_percentage'],['Duplicate candidates','duplicate_percentage']].map(([label,key])=>metrics.data_quality[key]!==undefined&&metrics.data_quality[key]!==null?<div className="quality-metric" key={key}><div><span>{label}</span><strong>{Number(metrics.data_quality[key]).toFixed(1)}%</strong></div><div className="quality-track"><i style={{width:Math.min(100,Math.max(0,Number(metrics.data_quality[key])))+'%'}}/></div></div>:null)}</div> : <Empty icon={FileCheck2} title="Aggregate quality percentages are not available" detail="No quality percentages were returned in the current metrics response. The dashboard will not estimate or fabricate them."/>}
    </section>
    <section className="panel module-panel"><div className="panel-heading"><div><h2>Recent ingestion outcomes</h2><p>Review actual job statuses and record counts.</p></div><button className="button-link" onClick={()=>setPage('Ingestion Jobs')}>Open jobs <ArrowRight size={15}/></button></div>
      {jobs.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>FILE</th><th>STATUS</th><th>PROCESSED</th><th>INSERTED</th><th>CREATED</th></tr></thead><tbody>{jobs.slice(0,8).map(j=><tr key={j.id}><td>{j.file_name||'Unnamed file'}</td><td><Pill value={j.status}/></td><td>{n(j.records_processed)}</td><td>{n(j.records_inserted)}</td><td>{when(j.created_at)}</td></tr>)}</tbody></table></div>:<Empty icon={Activity} title="No ingestion outcomes yet" detail="Submit a CSV or PDF dataset to begin tracking import outcomes."/>}
    </section>
  </div>;
  if (page === 'Warehouse') return <div className="module-page">
    <Heading eyebrow="DATA PLATFORM" title="Warehouse" description="Explore the registry records and import activity currently returned by the backend." action={<button className="button-secondary" onClick={()=>setPage('Registry Records')}>Open registry <ArrowRight size={15}/></button>}/>
    <div className="module-stats"><Stat icon={Database} label="Registry records" value={n(orgTotal)} detail="Total reported by registry API"/><Stat icon={HardDrive} label="Loaded in this view" value={n(orgs.length)} detail="Current page of records"/><Stat icon={Workflow} label="Ingestion jobs loaded" value={n(jobs.length)} detail="Recent job history"/></div>
    <section className="panel module-panel"><div className="panel-heading"><div><h2>Recent registry data</h2><p>Limited to records already returned by the authenticated registry API.</p></div><label className="module-search"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search records"/></label></div>
      {orgs.length ? <div className="table-scroll"><table className="data-table"><thead><tr><th>ORGANIZATION</th><th>REGISTRATION NUMBER</th><th>QUALITY STATUS</th><th>UPDATED</th></tr></thead><tbody>{orgs.filter(o=>[o.legal_name,o.registration_number].some(v=>String(v||'').toLowerCase().includes(search.toLowerCase()))).slice(0,12).map(o=><tr key={o.id}><td><strong>{o.legal_name||'Unnamed organization'}</strong></td><td>{o.registration_number||'—'}</td><td><Pill value={o.data_quality_status||o.status}/></td><td>{when(o.updated_at)}</td></tr>)}</tbody></table></div>:<Empty icon={HardDrive} title="Warehouse view is empty" detail="No registry records have been returned for this session. Import a dataset or check API connectivity."/>}
    </section>
    <div className="module-note"><LockKeyhole size={17}/><div><strong>Protected warehouse query endpoint</strong><p>Direct warehouse lookup requires a server-side service API key. The frontend does not contain or transmit an embedded internal key.</p></div></div>
  </div>;
  if (page === 'Validation Rules') return <div className="module-page">
    <Heading eyebrow="GOVERNANCE" title="Validation rules" description="Review validation safeguards implemented by the ingestion API. These are read-only summaries, not editable rules."/>
    <div className="module-stats"><Stat icon={ShieldCheck} label="File types" value="2" detail="CSV and PDF accepted"/><Stat icon={FileCheck2} label="Signature checks" value="Enabled" detail="Backend verifies file content"/><Stat icon={LockKeyhole} label="Idempotency" value="Supported" detail="Duplicate upload requests guarded"/></div>
    <section className="panel module-panel"><div className="panel-heading"><div><h2>Ingestion validation controls</h2><p>Rules summarized from current backend behavior.</p></div><ShieldCheck size={19}/></div>
      <div className="rule-list">{[
        ['File extension allowlist','Only CSV and PDF uploads are accepted by the upload endpoints.','Enforced'],
        ['PDF signature validation','The backend checks that uploaded PDF content begins with the expected PDF signature.','Enforced'],
        ['CSV binary-content check','CSV upload validation rejects NUL bytes in the inspected file prefix.','Enforced'],
        ['Size and object verification','Upload completion checks actual object size against the declared size and configured limit.','Enforced'],
        ['Idempotency protection','Repeated upload keys are checked against prior job metadata to prevent conflicting replays.','Enforced'],
        ['Row-level quality configuration','A dedicated configurable rule editor is not exposed in this frontend yet.','Not available in UI']
      ].map(([title,detail,status])=><article className="rule-row" key={title}><span className={status==='Enforced'?'rule-check':'rule-pending'}>{status==='Enforced'?<CheckCircle2 size={17}/>:<CircleHelp size={17}/>}</span><div><strong>{title}</strong><p>{detail}</p></div><span className={'rule-status '+(status==='Enforced'?'ok':'pending')}>{status}</span></article>)}</div>
    </section>
  </div>;
  if (page === 'Audit Logs') return <div className="module-page">
    <Heading eyebrow="ADMINISTRATION" title="Audit logs" description="Review ingestion activity visible to this workspace. This is not a substitute for the backend security audit log." action={<button className="button-secondary" onClick={refresh} disabled={loading}><RefreshCw size={15}/> Refresh</button>}/>
    <div className="module-note"><ShieldAlert size={17}/><div><strong>Security audit endpoint is not connected to this dashboard</strong><p>No security audit events are fabricated here. The activity below is derived from persisted ingestion jobs only.</p></div></div>
    <section className="panel module-panel"><div className="panel-heading"><div><h2>Ingestion activity</h2><p>Latest jobs returned by the API.</p></div><span className="record-count">{jobs.length} loaded</span></div>
      {jobs.length ? <div className="module-timeline">{jobs.slice(0,20).map(j=><article key={j.id}><span className="timeline-dot"><Activity size={14}/></span><div><div className="timeline-title"><strong>{j.file_name||'Unnamed import'}</strong><Pill value={j.status}/></div><p>{n(j.records_processed)} records processed · {n(j.records_inserted)} inserted</p><small>{when(j.created_at)} · Job {String(j.id||'').slice(0,12)}</small></div></article>)}</div>:<Empty icon={Activity} title="No ingestion activity yet" detail="Once imports are submitted, their persisted job activity will appear here."/>}
    </section>
  </div>;
  if (page === 'Settings') return <div className="module-page">
    <Heading eyebrow="WORKSPACE ADMINISTRATION" title="Settings" description="Review this frontend's active connection and session security behavior."/>
    <section className="panel module-panel"><div className="panel-heading"><div><h2>Connection</h2><p>Runtime configuration visible to the browser.</p></div><Database size={19}/></div>
      <div className="settings-list"><div><span>Datasource API base URL</span><strong>{import.meta.env.VITE_API_BASE_URL || (import.meta.env.DEV?'http://localhost:8000':'Same-origin')}</strong></div><div><span>API connection</span><Pill value={connected?'Connected':'Not connected'}/></div><div><span>Session model</span><strong>HttpOnly server-managed cookie</strong></div><div><span>CSRF protection</span><strong>In-memory token for state-changing requests</strong></div><div><span>Service API key in browser</span><strong className="safe-text">Not embedded</strong></div></div>
    </section>
    <div className="module-note"><ShieldCheck size={17}/><div><strong>Security boundary</strong><p>Internal service credentials must remain on the server. Registered source administration, warehouse query access and security audit retrieval should be exposed through explicitly authorized admin endpoints before being enabled in this UI.</p></div></div>
  </div>;
  return null;
}
