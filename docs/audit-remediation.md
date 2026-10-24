# Audit remediation summary

Every finding from the production-readiness audit and how it was addressed. All fixes have regression tests;
the suite runs on SQLite and on PostgreSQL, and CI enforces both.

| Finding | Fix |
| --- | --- |
| Worker could not start (`from .storage` in `ingestion/parser_csv.py`) | Import corrected; CI now lints all code and imports every entry point |
| Real data PDF in public repo | Removed, ignored; history purge steps in `security-incident-sample-pdf.md` (needs owner action) |
| `/metrics`, warehouse telemetry, `POST /sources` returned 500 | Missing imports added; source body validated with a Pydantic model |
| CSV export returned only a header | `yield_per` applied correctly; stream owns its session; export is audited |
| Customer keys reached shared data and ingestion | Customer keys are read-only lookup clients; tax PINs masked; internal endpoints refuse them |
| Key rotation could lose the key | Revoke + re-issue in one transaction |
| Long jobs recovered as stale and double-processed | Heartbeat at every checkpoint, timer-based checkpoints, lease-loss detection |
| Service key in the browser; hand-rolled JWT | HttpOnly session cookie + CSRF; PyJWT with required exp/sub, issuer, audience |
| Telemetry writes for unauthenticated calls; spoofable caller | Unauthenticated/throttled calls are not persisted; caller is prefixed `claimed:` and sanitised |
| Unbounded HMAC body buffering; blocking upload handler | Body capped before verification; upload runs in the threadpool; early `Content-Length` check |
| Supabase exposure of `api_keys` | Migration 011 enables RLS on every table, revokes browser-role privileges and default privileges |
| Export formula-injection guard, binary check | Real tab/CR/LF prefixes handled; NUL check fixed |
| Re-imports wrote needless versions and reset review state | Unchanged rows only refresh `last_seen_at`; review/duplicate flags preserved |
| `precedence` / `freshness_sla_hours` unused | Lower-precedence sources cannot overwrite authoritative records (audited); sources report `freshness_status` |
| Unescaped `LIKE`, empty queries, no index | Wildcards escaped, empty queries rejected, trigram index on PostgreSQL |
| Three drifting migration systems | Alembic is the source of truth; drift tests compare Alembic, SQL files and Supabase files with the models on PostgreSQL |
| Orphaned direct uploads | Signed `ContentLength`, mismatch rejected and object deleted, abandoned uploads expired by the worker |
| Idempotency replays ignored the payload | Replay requires the same file; a different file gets `409` |
| One bad row failed the whole job | PostgreSQL savepoint per row; conflicts are skipped and recorded |
| CI red (compose, tab test, narrow lint) | Compose gains Redis and a shared DB; test fixed; lint covers everything; PostgreSQL job and dependency audits added |
| Frontend: unpinned deps, no lockfile, dead default API URL, no CSP | Exact versions + lockfile (`npm ci`), required build arg, CSP/HSTS headers |
| Vulnerable pypdf, duplicate env files, README `\n` bugs | pypdf 6.x, single `.env.example`, README fixed, dev/test deps split out |

## Known boundaries (not defects)

- `src/resilience.py` (circuit breaker/retry) is intentionally not wired in yet; no external provider calls exist.
- Dashboard sessions are stateless; see `internal-api-security.md` for revocation limits.
- Per-process login and customer rate limits need Redis (`REDIS_URL`) to be shared across instances.
- Row savepoints add per-row overhead on PostgreSQL; set `INGESTION_ROW_SAVEPOINTS=false` to trade isolation for speed.
