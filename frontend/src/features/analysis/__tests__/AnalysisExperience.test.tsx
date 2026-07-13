import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router';
import { renderWithProviders } from '@/test/renderWithProviders';
import { AnalysisListPage } from '../pages/AnalysisListPage';
import { AnalysisRunPage } from '../pages/AnalysisRunPage';

describe('analysis preview experience', () => {
  afterEach(() => vi.restoreAllMocks());

  it('shows complete, processing, failed, empty, loading, and unavailable examples', () => {
    renderWithProviders(<AnalysisListPage />);

    expect(screen.getByText(/sample data · analysis preview/i)).toBeVisible();
    expect(screen.getByText('COMPLETE')).toBeVisible();
    expect(screen.getByText('PROCESSING')).toBeVisible();
    expect(screen.getByText('FAILED')).toBeVisible();
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
});
