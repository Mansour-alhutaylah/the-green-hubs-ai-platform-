import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/renderWithProviders';
import { LoginPage } from '@/features/auth/pages/LoginPage';

const EN_HERO_HEADING = 'Sustainability intelligence, grounded in evidence.';
const EN_HERO_SUPPORTING =
  'Manage documents, analyses, and evidence-grounded insights in one secure workspace.';
const AR_HERO_HEADING = 'ذكاء استدامة قائم على الأدلة';
const AR_HERO_SUPPORTING =
  'أدر المستندات والتحليلات والرؤى المستندة إلى الأدلة في مساحة عمل آمنة واحدة.';

describe('Login hero copy — single active locale only', () => {
  it('shows only English hero copy by default', async () => {
    renderWithProviders(<LoginPage />, { initialEntries: ['/login'] });

    expect(await screen.findByText(EN_HERO_HEADING)).toBeInTheDocument();
    expect(screen.getByText(EN_HERO_SUPPORTING)).toBeInTheDocument();
    expect(screen.queryByText(AR_HERO_HEADING)).not.toBeInTheDocument();
    expect(screen.queryByText(AR_HERO_SUPPORTING)).not.toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('dir', 'ltr');

    // The card heading ("Welcome back") must stay distinct from the hero
    // heading — no duplicated copy between the two.
    expect(await screen.findByRole('heading', { name: /^welcome back$/i })).toBeInTheDocument();
  });

  /* The MVP ships English only. These two tests previously asserted that
     Arabic *could* be activated, from storage and from the toggle; they now
     assert the opposite, which is the product decision: neither route may
     put the interface into a language this release does not finish. */
  it('renders English for a stored Arabic locale, rather than activating Arabic', async () => {
    window.localStorage.setItem('ghp:locale', 'ar');

    renderWithProviders(<LoginPage />, { initialEntries: ['/login'] });

    expect(await screen.findByText(EN_HERO_HEADING)).toBeInTheDocument();
    expect(screen.getByText(EN_HERO_SUPPORTING)).toBeInTheDocument();
    expect(screen.queryByText(AR_HERO_HEADING)).not.toBeInTheDocument();
    expect(screen.queryByText(AR_HERO_SUPPORTING)).not.toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('dir', 'ltr');
  });

  it('offers no language toggle while a single language ships', async () => {
    renderWithProviders(<LoginPage />, { initialEntries: ['/login'] });

    expect(await screen.findByText(EN_HERO_HEADING)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'العربية' })).not.toBeInTheDocument();
  });
});
