import {afterEach, describe, expect, it, vi} from 'vitest';
import {api} from './api.js';

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('API client', () => {
  it('sets JSON content type when a JSON body is sent', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ok: true}),
    });
    vi.stubGlobal('fetch', fetchMock);

    await api('/api/v1/example', {method: 'POST', body: JSON.stringify({name: 'Example'})});

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.get('Content-Type')).toBe('application/json');
  });

  it('does not override browser-generated multipart content type', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, status: 202});
    vi.stubGlobal('fetch', fetchMock);
    const form = new FormData();
    form.append('file', new Blob(['fictional,data'], {type: 'text/csv'}), 'fictional.csv');

    await api('/api/v1/ingestion/uploads', {method: 'POST', body: form});

    const [, options] = fetchMock.mock.calls[0];
    expect(options.headers.has('Content-Type')).toBe(false);
  });

  it('preserves environment mismatch code and readable guidance', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({
        detail: {
          code: 'API_KEY_ENVIRONMENT_MISMATCH',
          message: 'This sandbox key cannot be used in production.',
        },
      }),
    }));

    await expect(api('/api/v1/registry/lookup')).rejects.toMatchObject({
      status: 403,
      code: 'API_KEY_ENVIRONMENT_MISMATCH',
      message: 'This sandbox key cannot be used in production.',
    });
  });

  it('returns a useful error when a server failure is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      statusText: 'Bad Gateway',
      json: async () => { throw new SyntaxError('not JSON'); },
    }));

    await expect(api('/api/v1/registry/lookup')).rejects.toMatchObject({
      status: 502,
      message: 'Bad Gateway',
    });
  });
});

describe('session handling', () => {
  it('sends credentials and the in-memory CSRF token on unsafe requests only', async () => {
    const {setCsrfToken} = await import('./api.js');
    const fetchMock = vi.fn().mockResolvedValue({ok: true, status: 200});
    vi.stubGlobal('fetch', fetchMock);
    setCsrfToken('csrf-123');

    await api('/api/v1/sources', {method: 'POST', body: JSON.stringify({a: 1})});
    await api('/api/v1/organizations');

    const [, post] = fetchMock.mock.calls[0];
    const [, get] = fetchMock.mock.calls[1];
    expect(post.credentials).toBe('include');
    expect(post.headers.get('X-CSRF-Token')).toBe('csrf-123');
    expect(get.headers.has('X-CSRF-Token')).toBe(false);
    setCsrfToken('');
  });

  it('never attaches a service API key header', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ok: true, status: 200});
    vi.stubGlobal('fetch', fetchMock);
    await api('/api/v1/organizations');
    expect(fetchMock.mock.calls[0][1].headers.has('X-API-Key')).toBe(false);
  });
});
