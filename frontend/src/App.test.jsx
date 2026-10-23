import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('./api.js', () => ({ api: vi.fn() }));

import { api } from './api.js';
import { APIKeysPage } from './App.jsx';

const jsonResponse = (body) => ({ json: async () => body });

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  api.mockImplementation(async (path, options = {}) => {
    const method = options.method || 'GET';
    if (path === '/api/v1/admin/api-keys' && method === 'POST') {
      return jsonResponse({
        item: {
          id: 'key-test-1',
          name: 'Test sandbox key',
          environment: 'sandbox',
          key_prefix: 'pg_sandbox_abc123',
          scopes: ['registry:read'],
          status: 'active',
          created_at: '2026-10-23T10:00:00Z',
        },
        secret: 'pg_sandbox_abc123_one-time-test-secret',
        warning: 'Copy this secret now. It cannot be retrieved again.',
      });
    }
    if (path === '/api/v1/admin/api-keys') {
      return jsonResponse({ items: [], count: 0 });
    }
    if (path.startsWith('/api/v1/admin/security-events')) {
      return jsonResponse({ items: [], count: 0 });
    }
    throw new Error(`Unexpected API request: ${method} ${path}`);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('API key management page', () => {
  it('keeps operator credentials in memory and reveals a new secret after creation', async () => {
    render(<APIKeysPage />);

    fireEvent.change(screen.getByLabelText('Operator bearer token'), {
      target: { value: 'operator-test-token' },
    });
    fireEvent.click(screen.getByRole('button', { name: /unlock key management/i }));

    await screen.findByText('Operator access verified.');
    expect(localStorage.length).toBe(0);

    fireEvent.click(screen.getByRole('button', { name: /generate sandbox key/i }));
    const secretInput = await screen.findByLabelText('New API key secret');
    expect(secretInput.value).toBe('pg_sandbox_abc123_one-time-test-secret');
    expect(screen.getByText(/copy your new api key now/i)).toBeTruthy();
    expect(localStorage.length).toBe(0);
    expect(api).toHaveBeenCalledWith('/api/v1/admin/api-keys', expect.objectContaining({
      method: 'POST',
      headers: { Authorization: 'Bearer operator-test-token' },
    }));
  });

  it('shows a useful error when operator authentication fails', async () => {
    api.mockRejectedValueOnce(new Error('Valid operator bearer token required'));
    render(<APIKeysPage />);
    fireEvent.change(screen.getByLabelText('Operator bearer token'), {
      target: { value: 'invalid-token' },
    });
    fireEvent.click(screen.getByRole('button', { name: /unlock key management/i }));
    await waitFor(() => expect(screen.getByText(/valid operator bearer token required/i)).toBeTruthy());
  });
});
