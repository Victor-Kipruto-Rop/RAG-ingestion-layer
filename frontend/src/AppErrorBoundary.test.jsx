import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import AppErrorBoundary from './AppErrorBoundary.jsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('AppErrorBoundary', () => {
  it('renders children when the dashboard is healthy', () => {
    render(<AppErrorBoundary><p>Dashboard ready</p></AppErrorBoundary>);
    expect(screen.getByText('Dashboard ready')).toBeTruthy();
  });

  it('shows a safe recovery message when a child crashes', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    function BrokenWidget() {
      throw new Error('must not expose this detail');
    }

    render(<AppErrorBoundary><BrokenWidget /></AppErrorBoundary>);
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText('The dashboard encountered a problem')).toBeTruthy();
    expect(screen.getByText(/Your data has not been confirmed as changed/)).toBeTruthy();
    expect(screen.queryByText('must not expose this detail')).toBeNull();
  });
});
