import test from "node:test";
import assert from "node:assert/strict";
import { PesaGuardClient, PesaGuardError, verifyWebhookSignature } from "../src/index.js";
import { createHmac } from "node:crypto";

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


test("webhook signature verifier accepts valid signatures and rejects tampering/replay", () => {
  const payload = Buffer.from('{"id":"evt_1"}');
  const secret = "whsec_test_secret";
  const timestamp = 1800000000;
  const signature = createHmac("sha256", secret).update(String(timestamp)).update(".").update(payload).digest("hex");
  const header = `t=${timestamp},v1=${signature}`;
  assert.equal(verifyWebhookSignature(payload, header, secret, { now: timestamp }), true);
  assert.equal(verifyWebhookSignature(Buffer.concat([payload, Buffer.from(" ")]), header, secret, { now: timestamp }), false);
  assert.equal(verifyWebhookSignature(payload, header, secret, { now: timestamp + 1000 }), false);
});


test("rejects arbitrary origins, URL paths and embedded credentials", () => {
  for (const baseUrl of [
    "https://attacker.example",
    "https://api.pesaguard.co.ke/path",
    "https://user:password@sandbox-api.pesaguard.co.ke",
    "https://sandbox-api.pesaguard.co.ke?forward=1",
  ]) {
    assert.throws(() => new PesaGuardClient({ apiKey: "pg_sandbox_test", environment: "sandbox", baseUrl }));
  }
});

test("custom localhost origins are sandbox-only", () => {
  assert.doesNotThrow(() => new PesaGuardClient({ apiKey: "pg_sandbox_test", baseUrl: "http://localhost:8000" }));
  assert.throws(() => new PesaGuardClient({ apiKey: "pg_live_test", environment: "production", baseUrl: "http://localhost:8000" }), /only with sandbox keys/);
});
