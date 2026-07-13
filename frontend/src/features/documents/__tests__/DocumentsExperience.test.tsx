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
    expect(screen.getByText('PENDING')).toBeInTheDocument();
    expect(screen.getByText('PROCESSING')).toBeInTheDocument();
    expect(screen.getByText('PROCESSED')).toBeInTheDocument();
    expect(screen.getByText('FAILED')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /q3 2025 sustainability report/i })).toHaveAttribute(
      'href',
      '/documents/doc-1',
    );
  });

  it.each(['PENDING', 'PROCESSING', 'PROCESSED', 'FAILED'] as const)(
    'communicates %s without relying on color alone',
    (status) => {
      renderWithProviders(<DocumentStatusBadge status={status} />);
      expect(screen.getByText(status)).toBeVisible();
    },
  );

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
    expect(screen.getByRole('list', { name: /sample documents/i })).toBeVisible();
  });
});
