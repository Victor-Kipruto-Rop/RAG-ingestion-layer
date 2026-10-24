import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import ToastPopup from './ToastPopup.jsx';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.useRealTimers(); });

describe('ToastPopup', () => {
  it('renders success messages with a timestamp and dismiss control', () => {
    const onClose = vi.fn();
    const { container } = render(<ToastPopup kind="success" message="API key created" onClose={onClose} />);
    expect(screen.getByRole('status').textContent).toContain('API key created');
    expect(screen.getByText('Success')).toBeTruthy();
    expect(container.querySelector('time[datetime]')).toBeTruthy();
    expect(container.querySelector('.dp-toast-popup.success')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /dismiss message/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('renders warnings and errors as red alert popups', () => {
    const { rerender, container } = render(<ToastPopup kind="warning" message="Production access is blocked" onClose={() => {}} />);
    expect(screen.getByRole('alert').textContent).toContain('Warning');
    expect(container.querySelector('.dp-toast-popup.warning')).toBeTruthy();
    rerender(<ToastPopup kind="error" message="Invalid verification code" onClose={() => {}} />);
    expect(screen.getByRole('alert').textContent).toContain('Invalid verification code');
    expect(container.querySelector('.dp-toast-popup.error')).toBeTruthy();
  });

  it('automatically dismisses after its configured lifetime', () => {
    vi.useFakeTimers();
    const onClose = vi.fn();
    render(<ToastPopup kind="success" message="Saved" onClose={onClose} duration={2500} />);
    vi.advanceTimersByTime(2500);
    expect(onClose).toHaveBeenCalledOnce();
  });
});
