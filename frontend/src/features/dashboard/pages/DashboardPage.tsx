import { Link } from 'react-router';
import { Avatar, EmptyState, Icon, SectionCard, StatusBadge } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { useAuth } from '@/features/auth/useAuth';
import { ROUTES } from '@/app/navigation/routePaths';
import type { StringKey } from '@/lib/i18n/strings/en';
import { cn } from '@/lib/utils/cn';
import { formatDateTime } from '@/lib/utils/formatDate';
import { useDashboardSnapshot } from '@/lib/data/hooks/useDashboardSnapshot';
import type {
  ActivityAction,
  DashboardAnalysisInsight,
  DashboardSnapshot,
  DocumentState,
} from '@/lib/data/contracts';
import { AnalysisActivityChart } from '../components/AnalysisActivityChart';
import { AnalysisSummaryDonut } from '../components/AnalysisSummaryDonut';
import { DashboardCard } from '../components/DashboardCard';
import { DashboardHero } from '../components/DashboardHero';
import { DashboardKpiCard } from '../components/DashboardKpiCard';
import { DocumentStatusPip, ComplianceStatusPip } from '../components/StatusPip';
import { CoachmarksSequence } from '../CoachmarksSequence';

const ACTIVITY_ACTION_KEY: Record<ActivityAction, StringKey> = {
  uploaded: 'dashboard.activity.uploaded',
  approved: 'dashboard.activity.approved',
  viewed: 'dashboard.activity.viewed',
  published: 'dashboard.activity.published',
};

const DOCUMENT_RAIL: Record<DocumentState, string> = {
  processed: 'before:bg-leaf-500',
  processing: 'before:bg-sky-700',
  pending: 'before:bg-gray-400',
  failed: 'before:bg-red-700',
};

/**
 * The executive workspace.
 *
 * Where its figures come from is decided by `useDashboardSnapshot`, not by
 * this page: a Preview build renders deterministic Preview fixtures, and a
 * Live build renders whatever a real source returns. There is no dashboard
 * endpoint on the Backend yet, so Live resolves to `unavailable` and this
 * page says so plainly.
 *
 * The audit found the previous version showing a fabricated 128 documents,
 * an 86% compliance score, and a named activity feed to *every* signed-in
 * user, real ones included, above a line describing that as "some metrics".
 * None of those numbers can be reached in Live mode any more: the page has
 * no fixture import to fall back to.
 */
export function DashboardPage() {
  const { user } = useAuth();
  const snapshot = useDashboardSnapshot();

  const data = snapshot.status === 'ready' ? snapshot.data : null;

  return (
    <div>
      <DashboardHero user={user} totals={data?.totals} />

      {snapshot.status === 'ready' ? (
        <DashboardSnapshotView snapshot={data!} isPartial={snapshot.coverage === 'partial'} />
      ) : (
        <DashboardStateNotice status={snapshot.status} />
      )}

      <CoachmarksSequence />
    </div>
  );
}

/** Every non-`ready` state, stated rather than filled in. `unavailable` is
 * the Live case today: the capability does not exist yet, which is a
 * different claim from "there is no data" or "something failed", and the
 * copy keeps them distinct. */
function DashboardStateNotice({
  status,
}: {
  status: 'loading' | 'empty' | 'error' | 'forbidden' | 'unavailable';
}) {
  const { t } = useLocale();

  const copy: Record<typeof status, { title: StringKey; description: StringKey }> = {
    loading: {
      title: 'dashboard.state.empty.title',
      description: 'dashboard.state.empty.description',
    },
    empty: {
      title: 'dashboard.state.empty.title',
      description: 'dashboard.state.empty.description',
    },
    error: {
      title: 'dashboard.state.error.title',
      description: 'dashboard.state.error.description',
    },
    forbidden: {
      title: 'dashboard.state.forbidden.title',
      description: 'dashboard.state.forbidden.description',
    },
    unavailable: {
      title: 'dashboard.unavailable.title',
      description: 'dashboard.unavailable.description',
    },
  };

  return (
    <SectionCard className="mt-4 rounded-xl border-leaf-300/60 sm:mt-5">
      <EmptyState
        title={t(copy[status].title)}
        description={t(copy[status].description)}
        action={
          status === 'unavailable' ? (
            <p className="text-meta text-gray-600">{t('dashboard.unavailable.detail')}</p>
          ) : undefined
        }
      />
    </SectionCard>
  );
}

function DashboardSnapshotView({
  snapshot,
  isPartial,
}: {
  snapshot: DashboardSnapshot;
  isPartial: boolean;
}) {
  const { t } = useLocale();

  return (
    <>
      {isPartial && (
        <p className="mt-4 text-meta font-semibold text-gray-600">{t('dashboard.state.partial')}</p>
      )}

      {snapshot.metrics.length > 0 && (
        <section className="mt-4 sm:mt-5" aria-labelledby="workspace-overview-heading">
          <h2 id="workspace-overview-heading" className="sr-only">
            {t('dashboard.hero.workspace')}
          </h2>
          <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:gap-4 min-[1440px]:grid-cols-4">
            {snapshot.metrics.map((metric) => (
              <DashboardKpiCard key={metric.id} metric={metric} />
            ))}
          </div>
        </section>
      )}

      <div className="mt-5 grid grid-cols-1 gap-5 xl:mt-6 xl:grid-cols-3 xl:gap-6">
        <div className="xl:col-span-2">
          <DashboardCard
            title={t('dashboard.section.analysisActivity')}
            icon="analysis"
            eyebrow={t('dashboard.section.insights')}
          >
            <AnalysisActivityChart series={snapshot.monthlyAnalysisActivity} />
          </DashboardCard>
        </div>
        <DashboardCard
          title={t('dashboard.section.analysisSummary')}
          icon="reports"
          eyebrow={t('dashboard.section.insights')}
        >
          <AnalysisSummaryDonut outcomes={snapshot.analysisOutcomes} />
        </DashboardCard>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:mt-6 xl:grid-cols-3 xl:gap-6">
        <div className="flex flex-col gap-5 xl:col-span-2 xl:gap-6">
          <DashboardCard
            title={t('dashboard.section.recentDocuments')}
            eyebrow={t('dashboard.section.operations')}
            icon="documents"
            tone="priority"
            viewAllHref={ROUTES.documents}
          >
            <ul className="space-y-2">
              {snapshot.recentDocuments.map((document) => (
                <li key={document.id}>
                  <Link
                    to={`/documents/${document.id}`}
                    className={cn(
                      'surface-lift relative grid gap-3 overflow-hidden rounded-l border border-line-200 bg-paper-50 px-4 py-3 before:absolute before:inset-y-0 before:start-0 before:w-1 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center',
                      DOCUMENT_RAIL[document.state],
                    )}
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-m bg-surface-0 text-leaf-700 shadow-card">
                        <Icon name="documents" size={19} />
                      </span>
                      <span className="min-w-0">
                        <span
                          className="block truncate text-body font-bold text-ink-900"
                          data-user-content
                        >
                          {document.filename}
                        </span>
                        <span
                          className="mt-0.5 block truncate text-caption text-gray-600"
                          data-user-content
                        >
                          {document.organizationName} ·{' '}
                          <time dir="ltr">{formatDateTime(document.updatedAt)}</time>
                        </span>
                      </span>
                    </span>
                    <span className="justify-self-start sm:justify-self-end">
                      <DocumentStatusPip state={document.state} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard
            title={t('dashboard.section.recentActivity')}
            icon="audit"
            eyebrow={t('dashboard.section.operations')}
          >
            <ol className="relative ms-3 border-s border-line-200 ps-6">
              {snapshot.activity.map((entry, index) => (
                <li key={entry.id} className="relative pb-5 last:pb-0">
                  <span
                    className="absolute -start-7 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-surface-0 bg-leaf-500 shadow-signal"
                    aria-hidden
                  />
                  <div className="flex items-start gap-3">
                    <Avatar name={entry.actorName} size={32} />
                    <div className="min-w-0 flex-1">
                      <p className="text-body text-ink-900" data-user-content>
                        {t(ACTIVITY_ACTION_KEY[entry.action], {
                          actor: entry.actorName,
                          doc: entry.documentFilename,
                        })}
                      </p>
                      <p className="mt-1 text-caption text-gray-600">
                        <time dir="ltr">{formatDateTime(entry.occurredAt)}</time> ·{' '}
                        {index === 0 ? t('dashboard.activity.latest') : t('dashboard.activity.history')}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </DashboardCard>
        </div>

        <aside className="flex flex-col gap-5 xl:gap-6" aria-label={t('dashboard.section.insights')}>
          <DashboardCard
            title={t('dashboard.section.recentAnalysis')}
            eyebrow={t('dashboard.section.insights')}
            icon="analysis"
            tone="mint"
            viewAllHref={ROUTES.analysis}
          >
            <ul className="space-y-3">
              {snapshot.recentAnalysis.map((insight, index) => (
                <li key={insight.id}>
                  <Link
                    to={`/analysis/${insight.id}`}
                    className={cn(
                      'block rounded-l border p-3 transition-colors hover:border-leaf-300 hover:bg-surface-0',
                      index === 0 ? 'border-leaf-300 bg-surface-0 shadow-card' : 'border-transparent',
                    )}
                  >
                    <span className="flex items-start justify-between gap-3">
                      <span
                        className="min-w-0 truncate text-body font-bold text-ink-900"
                        data-user-content
                      >
                        {insight.documentFilename}
                      </span>
                      <DocumentStatusPip state={insight.state} />
                    </span>
                    <span className="mt-1 block text-caption text-gray-600">
                      <InsightDetail insight={insight} />
                    </span>
                    {insight.progressPercent != null && (
                      <>
                        <progress
                          className="sr-only"
                          aria-label={insight.documentFilename}
                          max={100}
                          value={insight.progressPercent}
                        >
                          {insight.progressPercent}%
                        </progress>
                        <span
                          className="mt-2 block h-1 overflow-hidden rounded-full bg-line-200"
                          aria-hidden
                        >
                          <span
                            className="block h-full rounded-full bg-leaf-500"
                            style={{ width: `${insight.progressPercent}%` }}
                          />
                        </span>
                      </>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard
            title={t('dashboard.section.complianceStatus')}
            icon="frameworks"
            viewAllHref={ROUTES.frameworks}
          >
            <ul className="space-y-2">
              {snapshot.frameworks.map((framework) => (
                <li
                  key={framework.id}
                  className="flex items-center justify-between gap-3 rounded-m bg-tint-100 px-3 py-2.5"
                >
                  <p className="min-w-0 text-meta font-bold text-ink-900">{framework.name}</p>
                  <ComplianceStatusPip state={framework.state} />
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard title={t('dashboard.section.processingQueue')} icon="upload">
            <ol className="space-y-3">
              {snapshot.processingQueue.map((item, index) => (
                <li key={item.id} className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-m bg-forest-900 text-micro font-bold text-white">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-meta font-bold text-ink-900" data-user-content>
                      {item.filename}
                    </span>
                    <span className="block text-caption text-gray-600">
                      {t('dashboard.queue.eta', { minutes: item.etaMinutes })}
                    </span>
                  </span>
                  <StatusBadge tone="pending">QUEUED</StatusBadge>
                </li>
              ))}
            </ol>
          </DashboardCard>
        </aside>
      </div>
    </>
  );
}

function InsightDetail({ insight }: { insight: DashboardAnalysisInsight }) {
  const { t } = useLocale();

  if (insight.state === 'processing' && insight.progressPercent != null) {
    return <>{t('dashboard.insight.processing', { percent: insight.progressPercent })}</>;
  }
  if (insight.state === 'failed') {
    return <>{t('dashboard.insight.failed')}</>;
  }
  if (insight.extractedFigureCount != null && insight.flaggedForReviewCount != null) {
    return (
      <>
        {t('dashboard.insight.extracted', {
          figures: insight.extractedFigureCount,
          flagged: insight.flaggedForReviewCount,
        })}
      </>
    );
  }
  return <>{t('dashboard.insight.queued')}</>;
}
