// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import AppErrorBoundary from './AppErrorBoundary.jsx';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('AppErrorBoundary', () => {
  it('renders child content while no error has occurred', () => {
    render(
      <AppErrorBoundary>
        <p>Registry dashboard</p>
      </AppErrorBoundary>,
    );
    expect(screen.getByText('Registry dashboard')).toBeTruthy();
  });

  it('shows a safe recovery message after a child render error', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    function BrokenPanel() {
      throw new Error('sensitive request detail must not appear');
    }

    render(
      <AppErrorBoundary>
        <BrokenPanel />
      </AppErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText('The dashboard encountered a problem')).toBeTruthy();
    expect(screen.getByText(/Your data has not been confirmed as changed/)).toBeTruthy();
    expect(screen.queryByText(/sensitive request detail/)).toBeNull();
  });
});
