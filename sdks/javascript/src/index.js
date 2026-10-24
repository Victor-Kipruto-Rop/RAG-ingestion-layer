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
    const parsed = new URL(this.baseUrl);
    const otherEnvironment = environment === "sandbox" ? "production" : "sandbox";
    if (parsed.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(parsed.hostname)) {
      throw new TypeError("baseUrl must use HTTPS outside local development");
    }
    if (parsed.hostname === new URL(DEFAULT_BASE_URLS[otherEnvironment]).hostname) {
      throw new TypeError("API key environment does not match the selected base URL");
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
