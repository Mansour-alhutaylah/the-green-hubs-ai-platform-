import { Link } from 'react-router';
import { Icon } from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { findNavItem } from '@/app/navigation/navConfig';
import { useHasMinTier } from '@/features/rbac/useHasMinTier';
import { useWorkspace } from '@/features/organizations/workspace/WorkspaceContext';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';

/**
 * The dashboard's executive band.
 *
 * This replaced a full-bleed forest hero that ran roughly 300px tall
 * before a single figure appeared, pushing every metric below the fold. It
 * carried an eyebrow, a display heading, a welcome line, a description, an
 * email, three buttons, and an animated node graphic. All of that answered
 * "where am I", which the navigation rail already answers, and none of it
 * answered "what needs attention".
 *
 * What it states now, in one compact row: whose workspace this is, which
 * reporting period the figures below cover, when they were produced, and
 * the three things an executive actually starts from. The KPI row is
 * immediately beneath it, so the first viewport opens on evidence rather
 * than on a greeting.
 *
 * Preview disclosure is deliberately *not* repeated here. The shell
 * already renders one unmissable global Preview ribbon, and the KPI row
 * carries a sample-data label on the figures themselves. A third warning
 * in the most visually dominant element on the page trains a reviewer to
 * stop reading warnings.
 */
export function ExecutiveHeader({
  reportingPeriod,
  generatedAt,
}: {
  /** Preview supplies its authored period. Live has no reporting-period
   * endpoint, so it passes nothing and the chip is not rendered. */
  reportingPeriod?: string;
  generatedAt?: string;
}) {
  const { t } = useLocale();
  const workspace = useWorkspace();
  const canUpload = useHasMinTier(findNavItem('upload').minTier);

  const workspaceName = workspace.organization?.name ?? null;

  return (
    <header className="rounded-xl border border-line-200 bg-surface-0 px-4 py-4 shadow-card sm:px-6 sm:py-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          {/* The eyebrow carries the framing; the `h1` stays "Dashboard".
              The nav item, the document title, and the page heading must
              name the page identically, or a reader navigating by heading
              lands somewhere that does not match the link they followed. */}
          <p className="type-label text-leaf-700">{t('dashboard.executive.title')}</p>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <h1 className="text-panel font-bold text-forest-900 sm:text-title">
              {t('nav.dashboard')}
            </h1>
            {workspaceName && (
              <span
                className="min-w-0 truncate rounded-full border border-line-200 bg-tint-100 px-2.5 py-0.5 text-caption font-semibold text-forest-900"
                data-user-content
              >
                {workspaceName}
              </span>
            )}
          </div>

          <p className="mt-1.5 max-w-2xl text-meta text-gray-600">
            {t('dashboard.executive.subtitle')}
          </p>

          <dl className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-caption text-gray-600">
            {reportingPeriod && (
              <div className="flex items-center gap-1.5">
                <dt className="font-semibold text-ink-900">
                  {t('dashboard.executive.period')}
                </dt>
                <dd>{reportingPeriod}</dd>
              </div>
            )}
            {generatedAt && (
              <div className="flex items-center gap-1.5">
                <dt className="font-semibold text-ink-900">
                  {t('dashboard.executive.generated')}
                </dt>
                <dd>
                  <time dir="ltr" dateTime={generatedAt}>
                    {formatDateTime(generatedAt)}
                  </time>
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Three actions, no more. Each is a registered route. */}
        <div className="flex shrink-0 flex-wrap gap-2">
          <Link
            to={ROUTES.documents}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-m bg-forest-900 px-3.5 text-meta font-bold text-white transition-colors hover:bg-forest-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
          >
            <Icon name="documents" size={16} />
            {t('dashboard.executive.reviewEvidence')}
          </Link>
          <Link
            to={ROUTES.reports}
            className="inline-flex min-h-10 items-center justify-center gap-2 rounded-m border border-line-300 bg-surface-0 px-3.5 text-meta font-bold text-forest-900 transition-colors hover:bg-tint-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
          >
            <Icon name="reports" size={16} />
            {t('dashboard.executive.openReports')}
          </Link>
          {canUpload && (
            <Link
              to={ROUTES.documentUpload}
              className="inline-flex min-h-10 items-center justify-center gap-2 rounded-m border border-line-300 bg-surface-0 px-3.5 text-meta font-bold text-forest-900 transition-colors hover:bg-tint-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
            >
              <Icon name="upload" size={16} />
              {t('dashboard.executive.uploadSource')}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
