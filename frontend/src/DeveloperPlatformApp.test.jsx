import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import DeveloperPlatformApp from './DeveloperPlatformApp.jsx';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('DeveloperPlatformApp public landing', () => {
  it('renders the developer landing page when no developer session exists', async () => {
    vi.stubGlobal('fetch', vi.fn(async input => {
      const url = String(input);
      if (url.includes('/api/v1/developer/auth/config')) return new Response(JSON.stringify({
        signup_enabled: false, password_reset_enabled: false, password_min_length: 12,
        social_auth_enabled: false, google_enabled: false, github_enabled: false
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      if (url.includes('/api/v1/developer/platform/config')) return new Response(JSON.stringify({
        sandbox_base_url: 'https://sandbox-api.pesaguard.co.ke',
        production_base_url: 'https://api.pesaguard.co.ke',
        key_prefixes: { sandbox: 'pg_sandbox_', production: 'pg_live_' },
        sdk_languages: ['cURL', 'JavaScript', 'Python', 'PHP', 'Go', 'Java', 'Ruby', 'C#']
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      return new Response(JSON.stringify({ detail: 'Developer session is missing or expired' }), {
        status: 401, headers: { 'Content-Type': 'application/json' }
      });
    }));
    render(<DeveloperPlatformApp />);
    expect(await screen.findByRole('heading', { name: /connect your product/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /start building/i })).toBeTruthy();
    expect(screen.getAllByText(/pg_sandbox_/).length).toBeGreaterThan(0);
    expect(screen.getByText(/strict environment separation/i)).toBeTruthy();
  });
});
