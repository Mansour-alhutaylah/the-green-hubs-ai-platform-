import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/renderWithProviders';
import { DocumentsListPage } from '../pages/DocumentsListPage';
import { DocumentUploadPage } from '../pages/DocumentUploadPage';
import { DocumentCollectionState } from '../components/DocumentCollectionState';
import { DocumentStatusBadge } from '../components/DocumentStatusBadge';

describe('document experience', () => {
  afterEach(() => vi.restoreAllMocks());

  it('renders every processing status with visible text and sample labeling', () => {
    renderWithProviders(<DocumentsListPage />);

    expect(screen.getByText(/sample data/i)).toBeInTheDocument();
    expect(screen.getAllByText('Pending').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Processing').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Processed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /q3 2025 sustainability report/i })).toHaveAttribute(
      'href',
      '/documents/doc-1',
    );
  });

  it.each([
    ['PENDING', 'Pending'],
    ['PROCESSING', 'Processing'],
    ['PROCESSED', 'Processed'],
    ['FAILED', 'Failed'],
  ] as const)('communicates %s without relying on color alone', (status, label) => {
    renderWithProviders(<DocumentStatusBadge status={status} />);
    expect(screen.getByText(label)).toBeVisible();
  });

  it('renders loading, empty, and error states with accessible messaging', () => {
    const view = renderWithProviders(<DocumentCollectionState state="loading" />);
    expect(screen.getAllByRole('status', { name: /loading documents/i })).toHaveLength(4);

    view.rerender(<DocumentCollectionState state="empty" />);
    expect(screen.getByRole('heading', { name: /no documents in this demo workspace/i })).toBeVisible();

    view.rerender(<DocumentCollectionState state="error" />);
    expect(screen.getByText(/no backend request was attempted/i)).toBeVisible();
  });

  it('validates a selected PDF locally and never makes a backend request', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderWithProviders(<DocumentUploadPage />);

    const input = screen.getByLabelText(/select a pdf document/i);
    const file = new File(['%PDF-1.7 sample'], 'sample-report.pdf', {
      type: 'application/pdf',
    });
    await user.upload(input, file);

    expect(screen.getByText('VALIDATED')).toBeVisible();
    expect(screen.getByText(/local selection only/i)).toBeVisible();
    expect(screen.getByRole('button', { name: /upload unavailable in preview/i })).toBeDisabled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('uses RTL direction without changing document behavior', () => {
    window.localStorage.setItem('ghp:locale', 'ar');
    renderWithProviders(<DocumentsListPage />);

    expect(document.documentElement).toHaveAttribute('dir', 'rtl');
    expect(screen.getByRole('list', { name: /مستندات بيئة العمل/ })).toBeVisible();
  });

  it('filters by status tab, search, and engagement, and paginates the results', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DocumentsListPage />);

    // 9 seeded rows, 5 per page -> a second page exists.
    expect(screen.getByText('Showing 1–5 of 9')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '2' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '2' }));
    expect(screen.getByText('Showing 6–9 of 9')).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Failed' }));
    expect(screen.getByText(/showing 1–2 of 2/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'All' }));
    await user.type(screen.getByLabelText(/search documents/i), 'Scope 1');
    expect(screen.getByText(/showing 1–1 of 1/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /scope 1 emissions ledger/i })).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/search documents/i));
    await user.selectOptions(
      screen.getByLabelText(/filter by engagement/i),
      'FY 2026 sustainability disclosure',
    );
    expect(screen.getByText(/showing 1–3 of 3/i)).toBeInTheDocument();
  });
});
