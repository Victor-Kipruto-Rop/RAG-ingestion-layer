import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('./api.js', () => ({ api: vi.fn() }));
import { api } from './api.js';
import { ManualReviewPage } from './App.jsx';

const response = (body) => ({ json: async () => body });

beforeEach(() => {
  vi.clearAllMocks();
  api.mockImplementation(async (path, options = {}) => {
    if (path === '/api/v1/reviews/queue?limit=100') {
      return response({ items: [{
        organization_id: 'org-review-1',
        legal_name: 'Example Test Limited',
        registration_number: 'CPR-12345',
        source_name: 'fictional-fixture',
        data_quality_status: 'UNREVIEWED',
      }], total: 1, count: 1 });
    }
    if (path === '/api/v1/reviews/org-review-1/decisions' && options.method === 'POST') {
      return response({ item: { decision: 'not_duplicate' } });
    }
    throw new Error(`Unexpected request: ${options.method || 'GET'} ${path}`);
  });
});

afterEach(() => vi.restoreAllMocks());

describe('manual review page', () => {
  it('loads the review queue and submits an auditable decision', async () => {
    render(<ManualReviewPage request={api} />);
    expect(await screen.findByText('Example Test Limited')).toBeTruthy();

    fireEvent.change(screen.getByLabelText('Decision for Example Test Limited'), {
      target: { value: 'not_duplicate' },
    });
    fireEvent.change(screen.getByLabelText('Reason for Example Test Limited'), {
      target: { value: 'Registration number reviewed against the test source.' },
    });
    fireEvent.click(screen.getByRole('button', { name: /save decision/i }));

    await waitFor(() => expect(api).toHaveBeenCalledWith(
      '/api/v1/reviews/org-review-1/decisions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          decision: 'not_duplicate',
          reason: 'Registration number reviewed against the test source.',
        }),
      }),
    ));
    expect(await screen.findByText(/review decision saved/i)).toBeTruthy();
  });

  it('requires a meaningful reason before submitting', async () => {
    render(<ManualReviewPage request={api} />);
    await screen.findByText('Example Test Limited');
    fireEvent.click(screen.getByRole('button', { name: /save decision/i }));
    expect(await screen.findByRole('alert')).toBeTruthy();
    expect(api).not.toHaveBeenCalledWith('/api/v1/reviews/org-review-1/decisions', expect.anything());
  });
});
