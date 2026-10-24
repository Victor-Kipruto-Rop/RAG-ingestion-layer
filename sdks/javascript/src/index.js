import { createHmac, timingSafeEqual } from "node:crypto";
const DEFAULT_BASE_URLS = Object.freeze({
  sandbox: "https://sandbox-api.pesaguard.co.ke",
  production: "https://api.pesaguard.co.ke",
});
const KEY_PREFIXES = Object.freeze({ sandbox: "pg_sandbox_", production: "pg_live_" });

export class PesaGuardError extends Error {
  constructor(message, { statusCode = null, responseBody = null } = {}) {
    super(message);
    this.name = "PesaGuardError";
    this.statusCode = statusCode;
    this.responseBody = responseBody;
  }
}

export class PesaGuardClient {
  constructor({ apiKey, environment = "sandbox", baseUrl, timeoutMs = 10000, fetchImpl = globalThis.fetch } = {}) {
    if (!Object.hasOwn(DEFAULT_BASE_URLS, environment)) throw new TypeError("environment must be sandbox or production");
    if (typeof apiKey !== "string" || !apiKey.startsWith(KEY_PREFIXES[environment])) {
      throw new TypeError(`${environment} keys must start with ${KEY_PREFIXES[environment]}`);
    }
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0 || timeoutMs > 120000) throw new TypeError("timeoutMs must be in (0, 120000]");
    if (typeof fetchImpl !== "function") throw new TypeError("A Fetch API implementation is required");
    this.apiKey = apiKey;
    this.environment = environment;
    this.baseUrl = (baseUrl || DEFAULT_BASE_URLS[environment]).replace(/\/$/, "");
    let parsed;
    try { parsed = new URL(this.baseUrl); } catch { throw new TypeError("baseUrl must be a valid absolute URL"); }
    if (parsed.username || parsed.password || parsed.search || parsed.hash || !["", "/"].includes(parsed.pathname)) {
      throw new TypeError("baseUrl must be an origin without credentials, path, query or fragment");
    }
    const localHost = ["localhost", "127.0.0.1"].includes(parsed.hostname.toLowerCase());
    if (parsed.protocol !== "https:" && !localHost) {
      throw new TypeError("baseUrl must use HTTPS outside local development");
    }
    if (localHost && environment !== "sandbox") {
      throw new TypeError("Local/custom API origins are allowed only with sandbox keys");
    }
    const expectedHost = new URL(DEFAULT_BASE_URLS[environment]).hostname;
    if (!localHost && parsed.hostname.toLowerCase() !== expectedHost) {
      throw new TypeError("API key environment does not match the approved base URL");
    }
    this.timeoutMs = timeoutMs;
    this.fetchImpl = fetchImpl;
  }

  async #get(resource, params) {
    const url = new URL(`/api/v1/registry/${resource}`, this.baseUrl);
    for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== null) url.searchParams.set(key, String(value));
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    let response;
    try {
      response = await this.fetchImpl(url, {
        method: "GET",
        redirect: "error",
        signal: controller.signal,
        headers: { "X-API-Key": this.apiKey, Accept: "application/json" },
      });
    } catch (error) {
      throw new PesaGuardError(error?.name === "AbortError" ? "PesaGuard API request timed out" : "Could not connect to PesaGuard API");
    } finally {
      clearTimeout(timeout);
    }
    let body;
    try { body = await response.json(); } catch { body = { message: "PesaGuard returned a non-JSON response" }; }
    if (!response.ok) {
      const detail = body && typeof body === "object" ? body.detail || body.message : null;
      throw new PesaGuardError(String(detail || "PesaGuard API request failed"), { statusCode: response.status, responseBody: body });
    }
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new PesaGuardError("PesaGuard returned an unexpected response format", { statusCode: response.status });
    return body;
  }

  search(query, { limit = 20 } = {}) {
    if (typeof query !== "string" || query.trim().length < 2) throw new TypeError("query must contain at least two characters");
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) throw new TypeError("limit must be an integer between 1 and 100");
    return this.#get("search", { q: query.trim(), limit });
  }

  lookup({ registrationNumber, taxPin } = {}) {
    if (Boolean(registrationNumber) === Boolean(taxPin)) throw new TypeError("Provide exactly one of registrationNumber or taxPin");
    return this.#get("lookup", registrationNumber ? { reg_no: registrationNumber } : { tax_pin: taxPin });
  }
}

export const PesaGuardEnvironments = DEFAULT_BASE_URLS;


export function verifyWebhookSignature(payload, signatureHeader, secret, { toleranceSeconds = 300, now = Math.floor(Date.now() / 1000) } = {}) {
  if (!(typeof payload === "string" || Buffer.isBuffer(payload)) || typeof secret !== "string" || !secret) return false;
  const fields = {};
  for (const part of String(signatureHeader || "").split(",")) {
    const separator = part.indexOf("=");
    if (separator < 1) continue;
    const key = part.slice(0, separator).trim();
    const value = part.slice(separator + 1).trim();
    if (!(key in fields)) fields[key] = value;
  }
  const timestamp = Number(fields.t);
  const supplied = fields.v1;
  if (!Number.isSafeInteger(timestamp) || typeof supplied !== "string" || !/^[a-f0-9]{64}$/i.test(supplied)) return false;
  if (!Number.isFinite(toleranceSeconds) || toleranceSeconds < 0 || Math.abs(now - timestamp) > toleranceSeconds) return false;
  const body = Buffer.isBuffer(payload) ? payload : Buffer.from(payload);
  const expected = createHmac("sha256", secret).update(String(timestamp)).update(".").update(body).digest();
  const actual = Buffer.from(supplied, "hex");
  return actual.length === expected.length && timingSafeEqual(actual, expected);
}
