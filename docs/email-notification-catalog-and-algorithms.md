# PesaGuard Developer Platform — Email Catalogue and Delivery Algorithms

**Status:** Specification and initial trigger implementation. Email delivery still depends on configured Resend or SMTP, verified sender domain, and provider-side event webhooks. Do not claim delivery until provider receipts are recorded.

## Delivery classes

- **Critical security:** verification, password reset, password changed, sign-in from a new session, session revoked, API-key created/revoked/rotated, production access decision. Send immediately; never suppress based on marketing preferences.
- **Operational:** production-access request received, webhook endpoint repeatedly failing, webhook secret rotation, ingestion/import failure, data quality threshold breach, rate-limit/quota threshold, service incident/recovery. Send on real state transitions and aggregate repeated failures.
- **Lifecycle/product:** welcome, getting-started, SDK examples, inactivity nudges, release notes, feature announcements, developer education. Respect preferences and unsubscribe state.
- **Marketing:** newsletters, offers, promotional campaigns, product surveys. Explicit opt-in, unsubscribe in every message, suppress unsubscribed/complaint/bounced addresses.

## Required email catalogue

| ID | Trigger | Algorithm / guard |
|---|---|---|
| account.verify_otp | Signup verification requested | Generate cryptographically random six-digit OTP; store HMAC digest only; expire quickly; invalidate prior active challenge; cap attempts; generic response avoids account enumeration. |
| account.welcome | Signup OTP succeeds | Send once after account + workspace commit; use account ID/event ID idempotency key. |
| account.password_reset_otp | Reset requested | Always return the same accepted response; send only for an active account; expire and attempt-limit the OTP; do not disclose account existence. |
| account.password_changed | Password reset succeeds or password changed | Revoke all active sessions in the same database transaction; send best-effort security notice after commit; never include password/OTP. |
| account.new_sign_in | New session created, especially OAuth/new device | Compare recent session IP digest/user agent; notify on a new fingerprint, not every refresh; include session-revocation path. |
| account.session_revoked | User/admin revokes a session | Notify when a session other than the current session is revoked; never send a secret or raw session token. |
| account.email_changed | Verified email change, when supported | Require re-authentication and OTP to old and new address; notify old address; revoke sessions and API tokens as policy requires. |
| account.mfa_enabled / mfa_disabled | MFA settings changed, when MFA exists | Notify immediately; require re-authentication; never email a reusable MFA seed. |
| api_key.created | Key persisted successfully | Send environment, label, scopes and key prefix only; never email full secret. |
| api_key.rotated | Rotation committed | Send new prefix, old-key grace deadline and revoke action; never email the full secret. |
| api_key.revoked | Revocation committed | Send key prefix, environment, actor/time and audit reference. |
| api_key.expiring | Key reaches 14/7/1-day expiry thresholds | Scheduled scan in UTC; one message per key/threshold; skip revoked keys. |
| api_key.anomalous_use | Risk rule sees suspicious use | Trigger on risk score/threshold and deduplicate by key + incident window; include safe metadata only. |
| production_access.request_received | Production access request committed | Acknowledge developer and notify reviewers; require idempotency by request ID; production remains disabled while pending. |
| production_access.approved | Reviewer approves request | Send approval, allowed production base URL, limits and activation steps; only after persisted approval and workspace verification. |
| production_access.rejected / action_required | Reviewer decision committed | Include safe reason and remediation route; do not issue production keys. |
| webhook.created | Webhook endpoint created | Confirm endpoint host, event subscriptions and signing secret prefix only; never send signing secret again. |
| webhook.delivery_degraded | Failure ratio or consecutive failures exceed threshold | Evaluate per endpoint over a rolling window; one alert per incident; include recent status codes and delivery-history link. |
| webhook.delivery_recovered | Delivery succeeds after degraded incident | Send one recovery message; close the incident/deduplication key. |
| webhook.secret_rotated | Signing secret rotated | Send only new prefix and cutover deadline; never include secret. |
| ingestion.failed | A persisted job enters terminal failure | Send once per job terminal transition; include job ID, source, sanitized failure category and retry/recovery link. |
| ingestion.recovered | Failed job later succeeds | Send one recovery notice if failure alert was sent. |
| data_quality.threshold_breached | Persisted quality result breaches configured threshold | Evaluate named rules, severity, sample window and cooldown; never include raw sensitive rows. |
| quota.warning / quota.exceeded | Usage crosses 80/100% of configured quota | Trigger only on upward threshold crossing; avoid per-request spam; reset after billing/usage window. |
| rate_limit.abuse | Abuse detector crosses threshold | Aggregate per key/workspace and incident window; include request ID/time range, not tokens. |
| incident.opened / incident.resolved | Status/incident system changes state | Notify opted-in operational contacts; deduplicate by incident ID; send recovery only for previously notified incidents. |
| release.notes | Published release tagged for developer audiences | Segment by subscribed product/language/SDK; one message per release; include changelog and migration notes. |
| developer.onboarding_nudge | Workspace created but key/docs/integration milestones incomplete | Schedule at 1/3/7 days; stop immediately when milestone reached, user unsubscribes, or account disabled; cap frequency. |
| developer.webinar / survey | Event or feedback campaign | Send only to consented segment; one per campaign; enforce global and campaign cooldowns. |
| holiday / seasonal greeting | Approved local holiday calendar | Send only to opted-in recipients who selected the relevant locale; use timezone-local send window; suppress marketing-unsubscribed recipients. |
| weekly_usage_digest | Weekly usage snapshot available | Only for users who enable digests; aggregate calls, error rate, webhook outcomes and quota; do not send on empty weeks unless configured. |

## Algorithm behind every send

1. **Observe a committed event.** Trigger after the business transaction commits; never send from an uncommitted mutation path.
2. **Normalize and classify.** Map the event to a stable template ID, delivery class, locale and recipient policy.
3. **Authorize the recipient.** Resolve the account/workspace owner and explicit operational contacts. Marketing requires recorded consent; transactional security mail does not depend on marketing consent.
4. **Deduplicate.** Use a stable idempotency key such as `template:event_id:recipient_id`. A retry must not create duplicate user-visible messages.
5. **Apply suppression and rate rules.** Respect unsubscribe/complaint/bounce status for marketing, event cooldowns for alerts, per-recipient frequency caps, and account state. Never suppress critical account-security mail due to marketing preferences.
6. **Render safe templates.** Escape user-supplied text, use a fixed sender domain, avoid secrets, OTPs except the requested OTP email, full API keys, signing secrets, raw tax IDs or imported sensitive records in logs.
7. **Queue durably.** Persist an outbox row in the same database transaction as the event. A worker claims rows with a lease, sends with bounded exponential backoff + jitter, and records attempts. Do not rely on in-process background tasks for guaranteed delivery.
8. **Call provider with idempotency.** Use provider idempotency where supported; retain provider message ID and safe error class.
9. **Track provider lifecycle.** Verify signed Resend/SMTP delivery, bounce, complaint and suppression webhooks; deduplicate provider event IDs. SMTP requires bounce tracking through the mail provider's event system.
10. **Retry or dead-letter.** Retry transient network/429/5xx failures with capped exponential backoff and jitter; do not retry permanent invalid-recipient/complaint errors. Move exhausted messages to a dead-letter state and alert operations.
11. **Measure.** Record queued/sent/delivered/bounced/complained/failed counts and latency, never message secrets or sensitive bodies.
12. **Audit.** Store template ID, recipient/account reference, event reference, provider ID, status and timestamps. Limit access and retention.

## Send windows and thresholds

- Security OTP: immediate; default 10-minute TTL and maximum 5 verification attempts (configurable within enforced bounds).
- Password/security events and production-access decisions: immediate.
- Webhook degradation: recommended threshold is 5 consecutive failures OR at least 50% failed deliveries across 10+ attempts in a 15-minute rolling window; one alert per endpoint incident.
- Quota warning: one email per 80% upward crossing; quota exceeded at 100%; do not repeat until usage resets or returns below a hysteresis boundary.
- Key expiry: 14, 7 and 1 day before expiry, once per key/threshold.
- Onboarding nudges: 24 hours, 72 hours and 7 days after workspace creation, only while the corresponding milestone remains incomplete.
- Weekly digest: Monday 09:00 in the user's configured timezone; only if opted in and there is meaningful activity.
- Marketing/holiday: user-selected locale/timezone, approved calendar, consent and unsubscribe suppression checked at send time.

## Current implementation and gaps

- Developer signup OTP and password-reset OTP are implemented using a database challenge, HMAC digest, expiry, attempt cap, Resend preferred / SMTP fallback.
- Developer sessions are persisted; logout and password reset revoke sessions. Session listing and per-session revocation endpoints exist.
- Production-access request events can already invoke subscribed webhooks.
- The generic transactional sender currently sends directly from request handlers. It is **not yet a durable transactional outbox** and provider delivery/bounce/complaint webhooks are not yet fully wired.
- Do not claim all catalogue events are sending until their business triggers, durable outbox, preference/consent storage, provider callbacks and tests are implemented.
- Sender domain should be verified with SPF/DKIM/DMARC. Secrets belong in the deployment secret store, never source control.
