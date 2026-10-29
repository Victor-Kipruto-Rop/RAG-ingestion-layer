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
  });
});


describe('DeveloperPlatformApp password recovery', () => {
  it('requests a password-reset OTP and advances to code verification', async () => {
    const requests = [];
    vi.stubGlobal('fetch', vi.fn(async (input, options = {}) => {
      const url = String(input);
      requests.push({ url, method: options.method || 'GET', body: options.body });
      if (url.includes('/api/v1/developer/auth/config')) return new Response(JSON.stringify({
        signup_enabled: true, password_reset_enabled: true, password_min_length: 12,
        social_auth_enabled: false, google_enabled: false, github_enabled: false
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
      if (url.includes('/api/v1/developer/auth/password-reset/request-otp')) return new Response(JSON.stringify({
        accepted: true, message: 'If an active account exists for this address, a reset code will arrive shortly.'
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404, headers: { 'Content-Type': 'application/json' } });
    }));

    render(<DeveloperPlatformApp />);
    fireEvent.click(await screen.findByRole('button', { name: /^sign in$/i }));
    fireEvent.click(await screen.findByRole('button', { name: /forgot password/i }));
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'developer@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue securely/i }));

    expect(await screen.findByRole('heading', { name: /verify reset code/i })).toBeTruthy();
    await waitFor(() => expect(requests.some(r => r.url.includes('/auth/password-reset/request-otp') && r.method === 'POST')).toBe(true));
    expect(screen.getByLabelText(/6-digit email code/i)).toBeTruthy();
  });
});


describe('DeveloperPlatformApp end-to-end authentication contract', () => {
  const readyConfig = {
    signup_enabled: true, password_reset_enabled: true, password_min_length: 12,
    social_auth_enabled: false, google_enabled: false, github_enabled: false
  };
  const platformConfig = {
    sandbox_base_url: 'https://sandbox-api.pesaguard.co.ke',
    production_base_url: 'https://api.pesaguard.co.ke',
    key_prefixes: { sandbox: 'pg_sandbox_', production: 'pg_live_' },
    sdk_languages: ['cURL', 'JavaScript', 'Python', 'PHP', 'Go', 'Java', 'Ruby', 'C#']
  };
  const authenticatedSession = {
    authenticated: true, csrf_token: 'csrf-test', access_token: 'access-test',
    user: { id: 'user-1', email: 'developer@example.com', display_name: 'Test Developer', email_verified: true },
    workspace: { id: 'workspace-1', name: 'Test Workspace', verified: false, production_access_approved: false }
  };

  function installAuthApiMock(requests) {
    let sessionChecks = 0;
    vi.stubGlobal('fetch', vi.fn(async (input, options = {}) => {
      const url = String(input);
      const method = options.method || 'GET';
      requests.push({ url, method, body: options.body });
      if (url.includes('/api/v1/developer/auth/config')) return new Response(JSON.stringify(readyConfig), { status: 200 });
      if (url.includes('/api/v1/developer/platform/config')) return new Response(JSON.stringify(platformConfig), { status: 200 });
      if (url.includes('/api/v1/developer/auth/session')) {
        sessionChecks += 1;
        return sessionChecks === 1
          ? new Response(JSON.stringify({ detail: 'Developer session is missing or expired' }), { status: 401 })
          : new Response(JSON.stringify(authenticatedSession), { status: 200 });
      }
      if (url.includes('/api/v1/developer/auth/password-reset/request-otp')) {
        return new Response(JSON.stringify({ accepted: true, message: 'If an active account exists, a reset code will arrive shortly.' }), { status: 202 });
      }
      if (url.includes('/api/v1/developer/auth/password-reset/confirm')) {
        return new Response(JSON.stringify({ updated: true, message: 'Password updated. Sign in again.' }), { status: 200 });
      }
      if (url.includes('/api/v1/developer/auth/login')) {
        return new Response(JSON.stringify(authenticatedSession), { status: 200 });
      }
      if (url.includes('/api/v1/developer/auth/logout')) return new Response(null, { status: 204 });
      if (url.includes('/api/v1/developer/')) return new Response(JSON.stringify({ items: [], total: 0, unread: 0 }), { status: 200 });
      if (url.includes('/api/v1/keys')) return new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 });
      return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404 });
    }));
  }

  it('submits developer login credentials to the matching backend endpoint and restores the workspace', async () => {
    const requests = [];
    installAuthApiMock(requests);
    render(<DeveloperPlatformApp />);
    fireEvent.click((await screen.findAllByRole('button', { name: /^sign in$/i }))[0]);
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'developer@example.com' } });
    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'A-long-unique-password-42' } });
    fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));

    expect(await screen.findByRole('heading', { name: /your integration layer/i })).toBeTruthy();
    await waitFor(() => expect(requests.some(r => r.url.includes('/api/v1/developer/auth/login') && r.method === 'POST')).toBe(true));
    expect(JSON.parse(requests.find(r => r.url.includes('/api/v1/developer/auth/login')).body))
      .toEqual({ email: 'developer@example.com', password: 'A-long-unique-password-42' });
  });

  it('completes password reset, clears the reset form, then allows login with the new password', async () => {
    const requests = [];
    installAuthApiMock(requests);
    render(<DeveloperPlatformApp />);
    fireEvent.click((await screen.findAllByRole('button', { name: /^sign in$/i }))[0]);
    fireEvent.click(await screen.findByRole('button', { name: /forgot password/i }));
    fireEvent.change(screen.getByLabelText(/email address/i), { target: { value: 'developer@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue securely/i }));
    expect(await screen.findByRole('heading', { name: /verify reset code/i })).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/6-digit email code/i), { target: { value: '123456' } });
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'A-new-unique-password-42' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'A-new-unique-password-42' } });
    fireEvent.click(screen.getByRole('button', { name: /continue securely/i }));
    expect(await screen.findByRole('heading', { name: /welcome back, developer/i })).toBeTruthy();
    expect(screen.getByLabelText(/^password$/i).value).toBe('');

    fireEvent.change(screen.getByLabelText(/^password$/i), { target: { value: 'A-new-unique-password-42' } });
    fireEvent.click(screen.getByRole('button', { name: /^sign in$/i }));
    expect(await screen.findByRole('heading', { name: /your integration layer/i })).toBeTruthy();

    const resetRequest = requests.find(r => r.url.includes('/auth/password-reset/request-otp'));
    const resetConfirm = requests.find(r => r.url.includes('/auth/password-reset/confirm'));
    const loginRequest = requests.find(r => r.url.includes('/auth/login'));
    expect(resetRequest.method).toBe('POST');
    expect(JSON.parse(resetConfirm.body)).toMatchObject({ email: 'developer@example.com', code: '123456', new_password: 'A-new-unique-password-42' });
    expect(JSON.parse(loginRequest.body)).toEqual({ email: 'developer@example.com', password: 'A-new-unique-password-42' });
  });
});
