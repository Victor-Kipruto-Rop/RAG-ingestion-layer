import React, { useState } from 'react';
import { API_BASE } from './api.js';
import { Activity, ArrowUpRight, BookOpen, Boxes, Database, FileCode2, GitBranch, KeyRound, LockKeyhole, Radio, ShieldCheck, Workflow } from 'lucide-react';

const PAGES = [
  { id: 'overview', title: 'Platform overview', icon: BookOpen },
  { id: 'api', title: 'API reference', icon: FileCode2 },
  { id: 'auth', title: 'Authentication', icon: LockKeyhole },
  { id: 'pipelines', title: 'Pipelines & data quality', icon: Workflow },
  { id: 'architecture', title: 'Architecture & stack', icon: Boxes },
  { id: 'operations', title: 'Operations & security', icon: ShieldCheck },
];

const STACK = [
  { name: 'API framework', value: 'FastAPI', note: 'Current service framework' },
  { name: 'Orchestration', value: 'Apache Airflow / Prefect', note: 'Integration choice; not claimed deployed' },
  { name: 'Storage & warehouse', value: 'PostgreSQL, BigQuery, Delta / Iceberg', note: 'PostgreSQL is current application store; others require explicit adapters and credentials' },
  { name: 'Streaming', value: 'Kafka / Flink', note: 'Optional streaming architecture; deployment must be verified' },
  { name: 'Transform & validate', value: 'dbt, Pandera, Great Expectations / Soda', note: 'Use per-pipeline validation contracts and persisted results' },
  { name: 'Secrets', value: 'Vault / AWS Secrets Manager / GCP Secret Manager', note: 'Choose one authoritative production secret store' },
  { name: 'Observability', value: 'Prometheus, Grafana, OpenTelemetry, ELK / Datadog', note: 'Prometheus metrics endpoint exists; dashboards and exporters require deployment verification' },
  { name: 'Infrastructure', value: 'Docker, Kubernetes, Terraform', note: 'Docker is used; Kubernetes and Terraform are deployment options, not assumed active' },
];

function Code({ children }) { return <pre className="docs-code"><code>{children}</code></pre>; }
function DocSection({ title, children }) { return <section className="docs-section"><h3>{title}</h3>{children}</section>; }

export default function DocumentationPage() {
  const [active, setActive] = useState('overview');
  const selected = PAGES.find(page => page.id === active) || PAGES[0];
  const Icon = selected.icon;
  return <div className="docs-layout">
    <aside className="docs-nav panel" aria-label="Documentation pages">
      <div className="docs-nav-heading"><BookOpen size={17}/><div><strong>Documentation</strong><small>Datasource handbook</small></div></div>
      {PAGES.map(page => { const ItemIcon = page.icon; return <button key={page.id} className={active === page.id ? 'docs-nav-item active' : 'docs-nav-item'} onClick={() => setActive(page.id)} aria-current={active === page.id ? 'page' : undefined}><ItemIcon size={16}/><span>{page.title}</span></button>; })}
      <a className="docs-external-link" href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">Open FastAPI Swagger <ArrowUpRight size={15}/></a>
      <a className="docs-external-link" href={`${API_BASE}/redoc`} target="_blank" rel="noreferrer">Open ReDoc <ArrowUpRight size={15}/></a>
    </aside>
    <article className="docs-article panel">
      <div className="docs-eyebrow"><Icon size={16}/> PESAGUARD DATASOURCE · DOCUMENTATION</div>
      <h1>{selected.title}</h1>
      {active === 'overview' && <>
        <p className="docs-lead">A registry-data service for importing authorized datasets, validating records, preserving provenance and exposing protected lookup APIs. It is a data source, not an authority that independently certifies a business.</p>
        <DocSection title="Core capabilities"><ul><li>Import authorized registry files and process them asynchronously.</li><li>Track ingestion jobs, row errors, source provenance and record changes.</li><li>Inspect data quality and warehouse access activity.</li><li>Manage scoped API keys through the API Keys workspace.</li><li>Expose operational health and protected Prometheus metrics.</li></ul></DocSection>
        <DocSection title="Where to start"><ol><li>Configure environment variables and start the local Docker Compose stack.</li><li>Sign in using the server-configured operator credential.</li><li>Register or configure a data source, then submit an authorized dataset.</li><li>Inspect ingestion jobs and data-quality results before using the lookup API.</li></ol></DocSection>
      </>}
      {active === 'api' && <>
        <p className="docs-lead">Use the live OpenAPI schema as the authoritative contract. Exact request and response schemas may evolve with the deployed version.</p>
        <DocSection title="API explorers"><p><a href={`${API_BASE}/openapi.json`} target="_blank" rel="noreferrer">OpenAPI JSON</a> · <a href="/docs" target="_blank" rel="noreferrer">Swagger UI</a> · <a href="/redoc" target="_blank" rel="noreferrer">ReDoc</a></p></DocSection>
        <DocSection title="API management workflow"><ul><li>Create a key in the appropriate environment and grant only required scopes.</li><li>Store the secret in a managed secret store; the full secret should only be shown at creation.</li><li>Set expiration and rotate keys before expiry or suspected compromise.</li><li>Revoke compromised keys and inspect the audit-event history.</li><li>Never send service credentials to browser code or commit them to source control.</li></ul></DocSection>
        <DocSection title="Request example"><Code>{'curl -H "Authorization: Bearer $PESAGUARD_ACCESS_TOKEN" "$PESAGUARD_API_BASE/api/v1/keys/me"'}</Code><p>Customer key-management routes require an access token issued by the configured trusted identity provider. The internal operator session is separate.</p></DocSection>
      </>}
      {active === 'auth' && <>
        <p className="docs-lead">Dashboard operator authentication uses a server-verified password, an HttpOnly session cookie and CSRF protection for state-changing requests.</p>
        <DocSection title="Current operator session"><ul><li>Session cookie: HttpOnly and SameSite=Strict; Secure must be enabled behind HTTPS in production.</li><li>Unsafe cookie-authenticated requests must include the CSRF token in <code>X-CSRF-Token</code>.</li><li>Sign-out clears the session cookie; session expiry is configured on the server.</li><li>Production login throttling requires shared Redis.</li></ul></DocSection>
        <DocSection title="Social login and account provisioning"><p>Google/GitHub OAuth, self-service registration, verified-email recovery and transactional email must only be enabled after provider applications, redirect URLs, trusted email policy and email delivery are configured. This dashboard must not treat an arbitrary OAuth identity as an administrator. Until those server-side prerequisites are configured, use the existing protected operator sign-in.</p></DocSection>
      </>}
      {active === 'pipelines' && <>
        <p className="docs-lead">Build repeatable, observable data flows with explicit source contracts, idempotency, validation and recoverable failures.</p>
        <DocSection title="Recommended processing sequence"><ol><li>Acquire source data using an authorized connector and versioned schema.</li><li>Persist source metadata and raw payload securely with provenance.</li><li>Normalize and deduplicate records using stable business keys.</li><li>Run Pandera or Soda / Great Expectations checks; persist rule version, result, severity and failed rows.</li><li>Use dbt for warehouse transformations where the warehouse adapter is installed and configured.</li><li>Record job state, retry bounded transient errors and route exhausted jobs to a dead-letter workflow.</li></ol></DocSection>
        <DocSection title="Orchestration and streaming"><p>Airflow or Prefect can schedule and coordinate batch workflows. Kafka and Flink are appropriate for event-driven streams when throughput and operational requirements justify them. These are architectural options until their services, adapters and deployment health are verified.</p></DocSection>
      </>}
      {active === 'architecture' && <>
        <p className="docs-lead">The following is the target technology map, not a claim that every component is installed or connected in the current deployment.</p>
        <div className="docs-stack-grid">{STACK.map(item => <section className="docs-stack-card" key={item.name}><strong>{item.name}</strong><span>{item.value}</span><small>{item.note}</small></section>)}</div>
        <DocSection title="Integration rule"><p>Every optional service needs a real adapter, configuration validation, health checks, secret handling, tests and operational ownership before it is represented as active. Do not silently substitute mock data or an in-memory production dependency.</p></DocSection>
      </>}
      {active === 'operations' && <>
        <p className="docs-lead">Operate the service using dependency-aware readiness, structured logs, traceable request IDs and an explicit recovery plan.</p>
        <DocSection title="Health and telemetry"><ul><li><code>/health/live</code> — process liveness.</li><li><code>/health/ready</code> — readiness against required database, Redis and object-storage dependencies.</li><li><code>/health</code> — safe dependency status summary.</li><li><code>/metrics</code> — Prometheus metrics protected by the configured metrics token.</li><li>Propagate <code>X-Correlation-ID</code> and never log credentials, access tokens, raw tax identifiers or sensitive personal payloads.</li></ul></DocSection>
        <DocSection title="Production release checklist"><ul><li>Run backend, PostgreSQL integration, frontend and container tests.</li><li>Verify tenant and role boundaries against a real PostgreSQL test environment.</li><li>Test backup restoration, worker recovery, retry exhaustion and rollback.</li><li>Configure alerts, dashboards, external uptime checks and load-test thresholds.</li><li>Use managed secrets and rotate OAuth, database, storage and signing credentials.</li><li>Keep release blocked until required CI checks are green and staging smoke tests pass.</li></ul></DocSection>
      </>}
    </article>
  </div>;
}
