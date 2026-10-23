import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api.js';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('datasource API client', () => {
  it('sets JSON content type for JSON request bodies', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);

    await api('/api/v1/example', { method: 'POST', body: JSON.stringify({ name: 'sample' }) });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.get('Content-Type')).toBe('application/json');
  });

  it('uses safe server error messages and handles structured API errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      json: async () => ({
        detail: {
          code: 'API_KEY_ENVIRONMENT_MISMATCH',
          message: 'This is a sandbox API key and can only be used with the sandbox datasource environment.',
        },
      }),
    }));

    await expect(api('/api/v1/registry/lookup')).rejects.toThrow(/sandbox API key/);
  });

  it('falls back to the HTTP status when an error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => { throw new Error('not JSON'); },
    }));

    await expect(api('/api/v1/registry/lookup')).rejects.toThrow('Request failed (502)');
  });
});
