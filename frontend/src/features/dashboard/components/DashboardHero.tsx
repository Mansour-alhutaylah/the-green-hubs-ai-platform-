import { Link } from 'react-router';
import { Icon } from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { findNavItem } from '@/app/navigation/navConfig';
import { useHasMinTier } from '@/features/rbac/useHasMinTier';
import type { AuthUser } from '@/features/auth/types';
import type { DashboardTotals } from '@/lib/data/contracts';
import { useLocale } from '@/lib/i18n/useLocale';

/**
 * The dashboard's identity band. It states who is signed in and where to go
 * next — never a metric it has not been given.
 *
 * `totals` is optional on purpose: when no source has supplied a snapshot
 * (Live today, since no dashboard endpoint exists), the counts strip is not
 * rendered at all rather than falling back to a placeholder figure. The
 * previous version hard-coded "4" documents and "3" analysis runs into the
 * markup, which were shown to every user regardless of their workspace.
 */
export function DashboardHero({
  user,
  totals,
}: {
  user?: AuthUser | null;
  totals?: DashboardTotals;
}) {
  const { t } = useLocale();
  const canUpload = useHasMinTier(findNavItem('upload').minTier);
  const displayName = user?.name ?? 'Green Hubs team';

  return (
    <section className="relative overflow-hidden rounded-xl border border-white/10 bg-forest-900 text-white shadow-brand">
      <div className="dashboard-network" aria-hidden>
        <span className="dashboard-node dashboard-node-primary" />
        <span className="dashboard-node dashboard-node-secondary" />
        <span className="dashboard-node dashboard-node-tertiary" />
      </div>

      <div className="relative z-10 max-w-3xl px-5 py-6 sm:px-7 sm:py-7 lg:pe-12">
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/7 px-3 py-1 text-caption font-semibold text-white/80">
            <span className="h-1.5 w-1.5 rounded-full bg-leaf-500 shadow-signal" aria-hidden />
            {t('dashboard.hero.workspace')}
          </span>
        </div>

        <p className="type-label mt-5 text-leaf-300">{t('dashboard.hero.eyebrow')}</p>
        <h1 className="mt-2 text-display text-white sm:text-hero">{t('nav.dashboard')}</h1>
        <p className="mt-2 text-title font-semibold text-white">
          {t('dashboard.hero.welcome', { name: displayName })}
        </p>
        <p className="mt-2 max-w-2xl text-body text-white/72">
          {t('dashboard.hero.description')}
        </p>
        {user && (
          <p className="mt-2 text-caption text-white/58" data-user-content>
            {user.email}
          </p>
        )}

        <div className="mt-5 flex flex-col gap-2 min-[420px]:flex-row">
          <Link
            to={ROUTES.documents}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-m bg-white px-4 text-meta font-bold text-forest-900 shadow-raise transition-transform hover:bg-mist-50 active:scale-[var(--scale-press)]"
          >
            <Icon name="documents" size={17} />
            {t('dashboard.hero.openDocuments')}
          </Link>
          <Link
            to={ROUTES.analysis}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-m border border-white/20 bg-white/7 px-4 text-meta font-bold text-white transition-colors hover:bg-white/12 active:scale-[var(--scale-press)]"
          >
            <Icon name="analysis" size={17} />
            {t('dashboard.hero.openAnalysis')}
          </Link>
          {canUpload && (
            <Link
              to={ROUTES.documentUpload}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-m border border-white/20 bg-white/7 px-4 text-meta font-bold text-white transition-colors hover:bg-white/12 active:scale-[var(--scale-press)]"
            >
              <Icon name="upload" size={17} />
              {t('dashboard.hero.openUpload')}
            </Link>
          )}
        </div>
      </div>

      {totals && (
        <dl className="relative z-10 grid border-t border-white/10 bg-black/10 min-[520px]:grid-cols-3">
          <HeroMetric
            label={t('dashboard.hero.documentsTracked')}
            value={String(totals.documentsTracked)}
          />
          <HeroMetric
            label={t('dashboard.hero.analysisRuns')}
            value={String(totals.analysisRuns)}
          />
          <HeroMetric
            label={t('dashboard.hero.workspaceState')}
            value={t('dashboard.hero.reviewReady')}
          />
        </dl>
      )}
    </section>
  );
}

function HeroMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-white/10 px-5 py-3.5 min-[520px]:border-s min-[520px]:first:border-s-0 sm:px-7">
      <dt className="text-caption font-medium text-white/58">{label}</dt>
      <dd className="mt-0.5 text-meta font-bold text-white">{value}</dd>
    </div>
  );
}
