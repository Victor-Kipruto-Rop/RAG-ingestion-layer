import { createHmac, timingSafeEqual } from 'node:crypto';

const BASE_URLS = {
  sandbox: 'https://sandbox-api.pesaguard.co.ke',
  production: 'https://api.pesaguard.co.ke',
};

export class PesaGuardClient {
  constructor({ apiKey = process.env.PESAGUARD_API_KEY, environment = process.env.PESAGUARD_ENV || 'sandbox', timeoutMs = 10000 } = {}) {
    if (!['sandbox', 'production'].includes(environment)) throw new Error('environment must be sandbox or production');
    const prefix = environment === 'sandbox' ? 'pg_sandbox_' : 'pg_live_';
    if (typeof apiKey !== 'string' || !apiKey.startsWith(prefix)) {
      throw new Error(`The selected ${environment} environment requires a ${prefix} API key`);
    }
    this.apiKey = apiKey;
    this.environment = environment;
    this.baseUrl = (process.env.PESAGUARD_BASE_URL || BASE_URLS[environment]).replace(/\/$/, '');
    const configured = new URL(this.baseUrl);
    if (configured.protocol !== 'https:' && process.env.NODE_ENV === 'production') throw new Error('Production SDK calls require HTTPS');
    if (configured.hostname !== new URL(BASE_URLS[environment]).hostname) throw new Error('Base URL does not match selected environment');
    this.timeoutMs = timeoutMs;
  }

  async request(path, { method = 'GET', query, body } = {}) {
    const url = new URL(path.replace(/^\//, ''), this.baseUrl + '/');
    if (query) for (const [key, value] of Object.entries(query)) url.searchParams.set(key, String(value));
    const response = await fetch(url, {
      method,
      headers: { 'X-API-Key': this.apiKey, Accept: 'application/json', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: AbortSignal.timeout(this.timeoutMs),
      redirect: 'error',
    });
    const text = await response.text();
    let payload;
    try { payload = text ? JSON.parse(text) : null; } catch { payload = { raw: text.slice(0, 2000) }; }
    if (!response.ok) throw new Error(`PesaGuard API returned HTTP ${response.status}: ${JSON.stringify(payload)}`);
    return payload;
  }

  searchRegistry(query, options = {}) {
    return this.request('/api/v1/registry/search', { query: { q: query, ...options } });
  }
}


export function verifyWebhookSignature(secret, rawBody, signatureHeader, { toleranceSeconds = 300, now = Date.now() / 1000 } = {}) {
  if (typeof secret !== 'string' || typeof signatureHeader !== 'string') return false;
  const body = Buffer.isBuffer(rawBody) ? rawBody : Buffer.from(rawBody ?? '');
  const values = {};
  for (const part of signatureHeader.split(',')) {
    const index = part.indexOf('=');
    if (index < 1) continue;
    const key = part.slice(0, index).trim();
    const value = part.slice(index + 1).trim();
    if ((key === 't' || key === 'v1') && !(key in values)) values[key] = value;
  }
  const timestamp = Number(values.t);
  if (!Number.isSafeInteger(timestamp) || typeof values.v1 !== 'string' || Math.abs(now - timestamp) > toleranceSeconds) return false;
  const expected = createHmac('sha256', secret).update(String(timestamp)).update('.').update(body).digest();
  let supplied;
  try { supplied = Buffer.from(values.v1, 'hex'); } catch { return false; }
  return supplied.length === expected.length && timingSafeEqual(expected, supplied);
}
