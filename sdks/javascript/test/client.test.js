import test from "node:test";
import assert from "node:assert/strict";
import { PesaGuardClient, PesaGuardError } from "../src/index.js";

test("rejects key/environment mismatch before making a request", () => {
  assert.throws(() => new PesaGuardClient({ apiKey: "pg_live_example", environment: "sandbox" }), /must start/);
  assert.throws(() => new PesaGuardClient({ apiKey: "pg_sandbox_example", environment: "sandbox", baseUrl: "https://api.pesaguard.co.ke" }), /does not match/);
});

test("search uses sandbox URL and X-API-Key header", async () => {
  let seen;
  const client = new PesaGuardClient({ apiKey: "pg_sandbox_test", fetchImpl: async (url, init) => {
    seen = { url: String(url), init };
    return new Response(JSON.stringify({ items: [], count: 0 }), { status: 200, headers: { "content-type": "application/json" } });
  }});
  const result = await client.search("example", { limit: 5 });
  assert.equal(result.count, 0);
  assert.match(seen.url, /^https:\/\/sandbox-api\.pesaguard\.co\.ke\/api\/v1\/registry\/search\?/);
  assert.equal(seen.init.headers["X-API-Key"], "pg_sandbox_test");
  assert.equal(new URL(seen.url).searchParams.get("limit"), "5");
});

test("lookup requires exactly one identifier", () => {
  const client = new PesaGuardClient({ apiKey: "pg_sandbox_test", fetchImpl: async () => new Response("{}") });
  assert.throws(() => client.lookup(), /exactly one/);
  assert.throws(() => client.lookup({ registrationNumber: "A", taxPin: "B" }), /exactly one/);
});

test("HTTP failures preserve a typed status and body", async () => {
  const client = new PesaGuardClient({ apiKey: "pg_sandbox_test", fetchImpl: async () => new Response(JSON.stringify({ detail: "forbidden" }), { status: 403 }) });
  await assert.rejects(() => client.search("example"), error => error instanceof PesaGuardError && error.statusCode === 403 && error.responseBody.detail === "forbidden");
});
