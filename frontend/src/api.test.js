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
