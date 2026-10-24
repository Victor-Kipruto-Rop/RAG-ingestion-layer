import test from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { PesaGuardClient, verifyWebhookSignature } from './client.js';

test('sandbox keys cannot be selected for production', () => {
  assert.throws(() => new PesaGuardClient({ apiKey: 'pg_sandbox_example', environment: 'production' }), /pg_live_/);
});

test('production keys cannot be selected for sandbox', () => {
  assert.throws(() => new PesaGuardClient({ apiKey: 'pg_live_example', environment: 'sandbox' }), /pg_sandbox_/);
});

test('base URL cannot cross environments', () => {
  const previous = process.env.PESAGUARD_BASE_URL;
  process.env.PESAGUARD_BASE_URL = 'https://sandbox-api.pesaguard.co.ke';
  try {
    assert.throws(() => new PesaGuardClient({ apiKey: 'pg_live_example', environment: 'production' }), /does not match/);
  } finally {
    if (previous === undefined) delete process.env.PESAGUARD_BASE_URL;
    else process.env.PESAGUARD_BASE_URL = previous;
  }
});

test('webhook signature validates exact raw body and timestamp tolerance', () => {
  const secret = 'webhook-test-secret';
  const body = Buffer.from('{"id":"evt_1","type":"webhook.test"}');
  const timestamp = 1800000000;
  const signature = createHmac('sha256', secret).update(String(timestamp)).update('.').update(body).digest('hex');
  const header = `t=${timestamp},v1=${signature}`;
  assert.equal(verifyWebhookSignature(secret, body, header, { now: timestamp }), true);
  assert.equal(verifyWebhookSignature(secret, Buffer.concat([body, Buffer.from(' ')]), header, { now: timestamp }), false);
  assert.equal(verifyWebhookSignature(secret, body, header, { now: timestamp + 301 }), false);
});
