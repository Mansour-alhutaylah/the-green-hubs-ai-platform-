import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Route, Routes } from 'react-router';
import { renderWithProviders } from '@/test/renderWithProviders';
import { AnalysisListPage } from '../pages/AnalysisListPage';
import { AnalysisRunPage } from '../pages/AnalysisRunPage';

describe('analysis preview experience', () => {
  afterEach(() => vi.restoreAllMocks());

  it('shows complete, processing, failed, empty, loading, and unavailable examples', () => {
    renderWithProviders(<AnalysisListPage />);

    expect(screen.getByText(/sample data · analysis preview/i)).toBeVisible();
    expect(screen.getAllByText('Completed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Processing').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Insufficient evidence').length).toBeGreaterThan(0);
    expect(screen.getByRole('heading', { name: /no analysis yet/i })).toBeVisible();
    expect(screen.getByRole('status', { name: /sample analysis is processing/i })).toBeVisible();
    expect(screen.getByRole('heading', { name: /analysis not available/i })).toBeVisible();
  });

  it('labels sample output and source references as unverified', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderWithProviders(
      <Routes>
        <Route path="/analysis/:runId" element={<AnalysisRunPage />} />
      </Routes>,
      { initialEntries: ['/analysis/run-1'] },
    );

    expect(await screen.findByText(/preview · not verified evidence/i)).toBeVisible();
    expect(screen.getByText(/sample reference · not verified evidence/i)).toBeVisible();
    expect(screen.getByRole('progressbar', { name: /sample analysis confidence/i })).toHaveAttribute(
      'value',
      '87',
    );
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('filters by status tab, search, and organization, and paginates the results', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AnalysisListPage />);

    // 9 seeded runs, 5 per page -> a second page exists.
    expect(screen.getByText('Showing 1–5 of 9')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '2' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '2' }));
    expect(screen.getByText('Showing 6–9 of 9')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Completed' }));
    expect(screen.getByText(/showing 1–4 of 4/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'All' }));
    await user.type(screen.getByLabelText(/search analysis runs/i), 'Scope 1');
    expect(screen.getByText(/showing 1–1 of 1/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /scope 1 emissions check/i })).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/search analysis runs/i));
    await user.selectOptions(
      screen.getByLabelText(/filter by organization/i),
      'Al-Riyadh Industrial Group',
    );
    expect(screen.getByText(/showing 1–4 of 4/i)).toBeInTheDocument();
  });
});
