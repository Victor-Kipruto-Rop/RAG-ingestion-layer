import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api.js';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('datasource API client', () => {
  it('returns successful responses and preserves response headers', async () => {
    const response = new Response(JSON.stringify({ status: 'ok' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json', 'X-Correlation-ID': 'test-correlation' },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));

    const result = await api('/health');
    expect(result.status).toBe(200);
    expect(result.headers.get('X-Correlation-ID')).toBe('test-correlation');
    await expect(result.json()).resolves.toEqual({ status: 'ok' });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/health$/),
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
  });

  it('sets JSON content type for JSON request bodies', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })));
    await api('/api/v1/admin/api-keys', { method: 'POST', body: JSON.stringify({ name: 'test' }) });
    const options = fetch.mock.calls[0][1];
    expect(options.headers.get('Content-Type')).toBe('application/json');
  });

  it('does not override multipart content type for FormData uploads', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 200 })));
    const body = new FormData();
    body.append('file', new Blob(['test']), 'test.csv');
    await api('/api/v1/ingestion/uploads', { method: 'POST', body });
    const options = fetch.mock.calls[0][1];
    expect(options.headers.has('Content-Type')).toBe(false);
  });

  it('surfaces structured API errors without losing the public error code', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: {
        code: 'API_KEY_ENVIRONMENT_MISMATCH',
        message: 'This is a sandbox API key and can only be used with the sandbox datasource environment.',
      },
    }), { status: 403, headers: { 'Content-Type': 'application/json' } })));

    await expect(api('/api/v1/registry/search')).rejects.toThrow(/sandbox API key/i);
  });

  it('falls back to the HTTP status text for non-JSON errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('unavailable', {
      status: 503,
      statusText: 'Service Unavailable',
    })));
    await expect(api('/health/ready')).rejects.toThrow(/Service Unavailable/);
  });
});
