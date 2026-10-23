import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import ApiKeysPanel from './ApiKeysPanel.jsx';
import { api } from './api.js';

vi.mock('./api.js', () => ({ api: vi.fn() }));

const jsonResponse = (body, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { 'Content-Type': 'application/json' },
});

function mockConnectedAccount(secret = 'pg_sandbox_test-secret-once') {
  api.mockImplementation(async (path, options = {}) => {
    if (path === '/api/v1/keys' && options.method === 'POST') {
      return jsonResponse({
        id: 'key-1', name: 'My integration', environment: 'sandbox',
        key_prefix: 'pg_sandbox_test', status: 'active', scopes: ['registry:read'],
        secret, created_at: new Date().toISOString(), expires_at: null,
        warning: 'Copy this secret now. It will not be shown again.',
      }, 201);
    }
    if (path === '/api/v1/keys') return jsonResponse({ items: [] });
    if (path.startsWith('/api/v1/keys/audit/events')) return jsonResponse({ items: [] });
    throw new Error('Unexpected test API request: ' + path);
  });
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  vi.clearAllMocks();
});

afterEach(() => cleanup());

describe('API key management panel', () => {
  it('stores the user access token in session storage, never local storage', async () => {
    api.mockImplementation(async (path) => {
      if (path === '/api/v1/keys') return jsonResponse({ items: [] });
      if (path.startsWith('/api/v1/keys/audit/events')) return jsonResponse({ items: [] });
      throw new Error('Unexpected test API request: ' + path);
    });
    render(<ApiKeysPanel />);
    fireEvent.change(screen.getByLabelText(/PesaGuard user access token/i), {
      target: { value: 'short-lived-test-token' },
    });
    fireEvent.click(screen.getByRole('button', { name: /connect account/i }));

    await waitFor(() => expect(screen.getByRole('heading', { name: /generate an API key/i })).toBeInTheDocument());
    expect(sessionStorage.getItem('pesaguard.datasource.user_access_token')).toBe('short-lived-test-token');
    expect(localStorage.getItem('pesaguard.datasource.user_access_token')).toBeNull();
  });

  it('reveals a generated secret once and clears it when the user confirms storage', async () => {
    mockConnectedAccount();
    render(<ApiKeysPanel />);
    fireEvent.change(screen.getByLabelText(/PesaGuard user access token/i), {
      target: { value: 'short-lived-test-token' },
    });
    fireEvent.click(screen.getByRole('button', { name: /connect account/i }));
    await waitFor(() => expect(screen.getByRole('heading', { name: /generate an API key/i })).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /generate sandbox key/i }));
    await waitFor(() => expect(screen.getByText('pg_sandbox_test-secret-once')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /I have stored the key/i }));
    expect(screen.queryByText('pg_sandbox_test-secret-once')).not.toBeInTheDocument();
  });

  it('shows an actionable error when the API rejects a token', async () => {
    api.mockRejectedValue(new Error('Access token has expired'));
    render(<ApiKeysPanel />);
    fireEvent.change(screen.getByLabelText(/PesaGuard user access token/i), {
      target: { value: 'expired-token' },
    });
    fireEvent.click(screen.getByRole('button', { name: /connect account/i }));
    await waitFor(() => expect(screen.getByText('Access token has expired')).toBeInTheDocument());
  });
});
