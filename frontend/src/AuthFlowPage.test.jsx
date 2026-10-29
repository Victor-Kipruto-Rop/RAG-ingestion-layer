// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import AuthFlowPage from './AuthFlowPage.jsx';
import { api } from './api.js';

vi.mock('./api.js', () => ({ api: vi.fn() }));

const response = body => ({ json: async () => body });

beforeEach(() => {
  vi.clearAllMocks();
  api.mockImplementation(async path => {
    if (path.endsWith('/signup/request-otp')) return response({ accepted: true });
    if (path.endsWith('/signup/verify-otp')) return response({ authenticated: true, csrf_token: 'csrf-test', identity_email: 'operator@example.com' });
    if (path.endsWith('/password-reset/request-otp')) return response({ accepted: true });
    if (path.endsWith('/password-reset/confirm')) return response({ reset: true });
    throw new Error('Unexpected API route: ' + path);
  });
});
afterEach(cleanup);

describe('operator authentication flows', () => {
  it('requests an email OTP and authenticates only after OTP verification', async () => {
    const onAuthenticated = vi.fn();
    render(<AuthFlowPage mode="signup" config={{ password_min_length: 12, otp_ttl_seconds: 600 }} onBack={vi.fn()} onAuthenticated={onAuthenticated} />);
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Test Operator' } });
    fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'operator@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'unique-password-2026' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'unique-password-2026' } });
    fireEvent.click(screen.getByRole('button', { name: /send verification code/i }));
    await waitFor(() => expect(screen.getByLabelText('Email verification code')).toBeTruthy());
    expect(onAuthenticated).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Email verification code'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: /verify email and create account/i }));
    await waitFor(() => expect(onAuthenticated).toHaveBeenCalledWith(expect.objectContaining({ authenticated: true, csrf_token: 'csrf-test' })));
  });

  it('completes the password reset request and confirmation flow', async () => {
    render(<AuthFlowPage mode="reset" config={{ password_min_length: 12, otp_ttl_seconds: 600 }} onBack={vi.fn()} onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'operator@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await waitFor(() => expect(screen.getByLabelText('Email verification code')).toBeTruthy());
    fireEvent.change(screen.getByLabelText('Email verification code'), { target: { value: '123456' } });
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'another-unique-password-2026' } });
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Password updated' })).toBeTruthy());
  });
});


  it('shows an actionable error when signup OTP delivery fails', async () => {
    api.mockRejectedValueOnce(new Error('Verification email could not be sent. Check mail configuration or try later.'));
    render(<AuthFlowPage mode="signup" config={{ password_min_length: 12, otp_ttl_seconds: 600 }} onBack={vi.fn()} onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Full name'), { target: { value: 'Test Operator' } });
    fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'operator@example.com' } });
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'unique-password-2026' } });
    fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'unique-password-2026' } });
    fireEvent.click(screen.getByRole('button', { name: /send verification code/i }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Verification email could not be sent'));
    expect(screen.queryByLabelText('Email verification code')).toBeNull();
  });

  it('shows a recoverable error when password reset request fails', async () => {
    api.mockRejectedValueOnce(new Error('Password reset is temporarily unavailable.'));
    render(<AuthFlowPage mode="reset" config={{ password_min_length: 12, otp_ttl_seconds: 600 }} onBack={vi.fn()} onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText('Work email'), { target: { value: 'operator@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('Password reset is temporarily unavailable'));
    expect(screen.queryByLabelText('Email verification code')).toBeNull();
  });
