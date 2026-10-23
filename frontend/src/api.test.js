import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api.js';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('datasource API client', () => {
  it('returns successful responses and sends JSON content type for JSON bodies', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    const response = await api('/health/live', {
      method: 'POST',
      body: JSON.stringify({ probe: true }),
    });

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.get('Content-Type')).toBe('application/json');
  });

  it('surfaces structured API error messages without losing the server status', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: 'API_KEY_ENVIRONMENT_MISMATCH', message: 'Sandbox keys cannot be used in production.' },
    }), {
      status: 403,
      headers: { 'Content-Type': 'application/json' },
    })));

    await expect(api('/api/v1/registry/search?q=example')).rejects.toThrow(
      'Sandbox keys cannot be used in production.',
    );
  });

  it('does not force a multipart content type when uploading a file', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response('{}', { status: 202 }));
    vi.stubGlobal('fetch', fetchMock);
    const form = new FormData();
    form.append('file', new Blob(['test']), 'sample.csv');

    await api('/api/v1/ingestion/uploads', { method: 'POST', body: form });

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.has('Content-Type')).toBe(false);
  });
});
