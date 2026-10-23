import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
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
    expect(screen.getByRole('button', { name: /reload dashboard/i })).toBeTruthy();
  });
});
