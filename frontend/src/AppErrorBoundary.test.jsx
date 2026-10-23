// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import AppErrorBoundary from './AppErrorBoundary.jsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function BrokenPanel() {
  throw new Error('fixture render failure');
}

describe('AppErrorBoundary', () => {
  it('shows a recoverable fallback instead of a blank dashboard', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <AppErrorBoundary>
        <BrokenPanel />
      </AppErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByRole('heading', { name: /dashboard encountered a problem/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /reload dashboard/i })).toBeTruthy();
    expect(screen.getByText(/your data has not been confirmed as changed/i)).toBeTruthy();
  });
});
