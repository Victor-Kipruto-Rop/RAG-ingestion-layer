// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('./api.js', () => ({ api: vi.fn() }));

import { api } from './api.js';
import ApiKeysPanel from './ApiKeysPanel.jsx';

const jsonResponse = body => new Response(JSON.stringify(body), {
  status: 200,
  headers: { 'Content-Type': 'application/json' },
});

beforeEach(() => {
  vi.clearAllMocks();
  api.mockImplementation(async path => {
    if (path === '/api/v1/keys') return jsonResponse({ items: [] });
    if (path === '/api/v1/keys/audit/events?limit=50') return jsonResponse({ items: [] });
    throw new Error(`Unexpected request: ${path}`);
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('ApiKeysPanel token handling', () => {
  it('keeps the user access token in component memory instead of web storage', async () => {
    const storageSet = vi.spyOn(Storage.prototype, 'setItem');
    render(<ApiKeysPanel />);

    fireEvent.change(screen.getByLabelText(/PesaGuard user access token/i), {
      target: { value: 'short-lived-test-access-token' },
    });
    fireEvent.click(screen.getByRole('button', { name: /connect account/i }));

    await screen.findByText(/your API keys/i);
    await waitFor(() => expect(api).toHaveBeenCalledWith('/api/v1/keys', expect.objectContaining({
      headers: expect.objectContaining({ Authorization: 'Bearer short-lived-test-access-token' }),
    })));

    expect(storageSet).not.toHaveBeenCalled();
    expect(screen.getByText(/kept in memory only/i)).toBeTruthy();
  });
});
