import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import AppErrorBoundary from './AppErrorBoundary.jsx';

function BrokenView() {
  throw new Error('private input should not be logged');
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('AppErrorBoundary', () => {
  it('shows a recoverable error state without exposing the exception text', () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<AppErrorBoundary><BrokenView /></AppErrorBoundary>);
    expect(screen.getByRole('alert').textContent).toContain('The dashboard encountered a problem');
    expect(screen.queryByText('private input should not be logged')).toBeNull();
    expect(errorSpy).toHaveBeenCalled();
    expect(JSON.stringify(errorSpy.mock.calls)).not.toContain('private input should not be logged');
  });

  it('offers a reload action from the fallback state', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const originalReload = window.location.reload;
    const reload = vi.fn();
    try {
      Object.defineProperty(window, 'location', { configurable: true, value: { ...window.location, reload } });
      render(<AppErrorBoundary><BrokenView /></AppErrorBoundary>);
      fireEvent.click(screen.getByRole('button', { name: /reload dashboard/i }));
      expect(reload).toHaveBeenCalledTimes(1);
    } finally {
      Object.defineProperty(window, 'location', { configurable: true, value: { ...window.location, reload: originalReload } });
    }
  });
});
