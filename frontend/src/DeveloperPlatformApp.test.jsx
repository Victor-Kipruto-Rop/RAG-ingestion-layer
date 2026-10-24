import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    const { container } = render(<DeveloperPlatformApp />);
    expect(await screen.findByRole('heading', { name: /connect your product/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /start building/i })).toBeTruthy();
    expect(screen.getAllByText(/pg_sandbox_/).length).toBeGreaterThan(0);
    expect(screen.getByText(/strict environment separation/i)).toBeTruthy();
    expect(container.querySelector('.dp-wind-scene')).toBeTruthy();
    expect(screen.getByText(/signed webhooks/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /start building/i }));
    const configWarning = await screen.findByRole('alert');
    expect(configWarning.className).toContain('warning');
    expect(configWarning.textContent).toContain('Registration is disabled');
    expect(screen.getByRole('button', { name: /dismiss message/i })).toBeTruthy();
  });
});


describe('DeveloperPlatformApp account onboarding', () => {
  it('submits the developer signup OTP request and transitions to verification', async () => {
    const requests = [];
    vi.stubGlobal('fetch', vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = options.method || 'GET';
      requests.push({ url, method, body: options.body });
      if (url.includes('/api/v1/developer/auth/config')) return new Response(JSON.stringify({
        signup_enabled: true, password_reset_enabled: true, password_min_length: 12,
        social_auth_enabled: true, google_enabled: true, github_enabled: true
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      if (url.includes('/api/v1/developer/platform/config')) return new Response(JSON.stringify({
        sandbox_base_url: 'https://sandbox-api.pesaguard.co.ke',
        production_base_url: 'https://api.pesaguard.co.ke',
        key_prefixes: { sandbox: 'pg_sandbox_', production: 'pg_live_' },
        sdk_languages: ['cURL', 'JavaScript', 'Python', 'PHP', 'Go', 'Java', 'Ruby', 'C#']
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      if (url.includes('/api/v1/developer/auth/session')) return new Response(JSON.stringify({
        detail: 'Developer session is missing or expired'
      }), { status: 401, headers: { 'Content-Type': 'application/json' } });
      if (url.includes('/api/v1/developer/auth/signup/request-otp')) return new Response(JSON.stringify({
        accepted: true, message: 'If registration is available, a verification code will arrive shortly.'
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } });
    }));

    render(<DeveloperPlatformApp />);
    fireEvent.click(await screen.findByRole('button', { name: /start building/i }));
    fireEvent.change(screen.getByLabelText(/full name/i), { target: { value: 'Test Developer' } });
    fireEvent.change(screen.getByLabelText(/workspace name/i), { target: { value: 'Test Workspace' } });
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'developer@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'A-long-unique-password-42' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'A-long-unique-password-42' } });
    fireEvent.click(screen.getByRole('button', { name: /send verification code/i }));

    expect(await screen.findByRole('heading', { name: /verify your email/i })).toBeTruthy();
    await waitFor(() => expect(requests.some(r => r.url.includes('/auth/signup/request-otp') && r.method === 'POST')).toBe(true));
    const request = requests.find(r => r.url.includes('/auth/signup/request-otp'));
    expect(JSON.parse(request.body)).toMatchObject({ email: 'developer@example.com', display_name: 'Test Developer', workspace_name: 'Test Workspace' });
    expect(screen.getByLabelText(/6-digit email code/i)).toBeTruthy();
    const successToast = screen.getByRole('status');
    expect(successToast.textContent).toContain('Success');
    expect(successToast.querySelector('time')).toBeTruthy();
    expect(screen.getByRole('button', { name: /dismiss message/i })).toBeTruthy();
  });
});
