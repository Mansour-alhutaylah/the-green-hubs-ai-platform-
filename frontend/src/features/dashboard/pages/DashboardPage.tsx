import { Link } from 'react-router';
import { Avatar, EmptyState, Icon, SectionCard, StatusBadge } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ROUTES } from '@/app/navigation/routePaths';
import type { StringKey } from '@/lib/i18n/strings/en';
import { cn } from '@/lib/utils/cn';
import { formatDateTime } from '@/lib/utils/formatDate';
import { useDashboardSnapshot } from '@/lib/data/hooks/useDashboardSnapshot';
import { isPreviewMode } from '@/lib/data/source';
import type {
  ActivityAction,
  DashboardAnalysisInsight,
  DashboardSnapshot,
  DocumentState,
} from '@/lib/data/contracts';
import { useExecutiveSummary } from '@/lib/data/hooks/useExecutiveData';
import { AnalysisActivityChart } from '../components/AnalysisActivityChart';
import { AnalysisSummaryDonut } from '../components/AnalysisSummaryDonut';
import { DashboardCard } from '../components/DashboardCard';
import { DashboardExecutiveView } from '../components/DashboardExecutiveView';
import { DashboardLiveView } from '../components/DashboardLiveView';
import { ExecutiveHeader } from '../components/ExecutiveHeader';
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
 * Two dashboards, deliberately not one. They render different contracts
 * because they can prove different things, and forcing them through a
 * single component is how a synthetic figure ends up in a real card.
 *
 * - **Preview** renders `DashboardSnapshot` (deterministic fixtures) plus
 *   the F2A breakdowns — processing states, the evidence-review lifecycle,
 *   an engagement roll-up, readiness — a complete demonstration workspace.
 * - **Live** renders `DashboardLiveSummary`: exact `total` figures from
 *   `GET /documents` and `GET /engagements`, the real five most recent
 *   documents, the caller's real organization name, and compact,
 *   specifically-named unavailable states for the four capabilities no
 *   endpoint provides. It replaces the single large "metrics are not
 *   connected" placeholder F1 shipped, which was truthful but told a real
 *   user nothing they could use.
 *
 * The audit that produced F1 found this page showing a fabricated 128
 * documents, an 86% compliance score, and a named activity feed to *every*
 * signed-in user. None of that is reachable in Live: the Live branch's
 * dependency graph contains no fixture module, so there is nothing
 * synthetic for a failure to fall back to.
 *
 * The mode is a build-time constant, so the branch below is stable for the
 * life of a build and the two branches never share hook state.
 */
export function DashboardPage() {
  return (
    // The bottom padding is the safe area for the coachmarks panel, which
    // is `position: fixed` over the bottom-end corner. Without it the panel
    // covers the last card in the final column on a short viewport.
    <div className="pb-28 sm:pb-32">
      {isPreviewMode() ? <PreviewDashboard /> : <LiveDashboard />}
      <CoachmarksSequence />
    </div>
  );
}

/**
 * The Live branch. The header carries no reporting period and no
 * generated-at timestamp: neither has an endpoint, so those chips are
 * omitted rather than filled with a plausible value. The figures below
 * are exact `total` counts in their own cards, where a failed one says
 * "Unavailable" instead of "0".
 */
function LiveDashboard() {
  return (
    <>
      <ExecutiveHeader />
      <DashboardLiveView />
    </>
  );
}

function PreviewDashboard() {
  const snapshot = useDashboardSnapshot();
  const executive = useExecutiveSummary();

  const data = snapshot.status === 'ready' ? snapshot.data : null;
  const isPartial = snapshot.status === 'ready' && snapshot.coverage === 'partial';
  const summary = executive.status === 'ready' ? executive.data : null;

  return (
    <>
      <ExecutiveHeader
        reportingPeriod={summary?.reportingPeriod}
        generatedAt={summary?.generatedAt}
      />

      {summary && (
        <DashboardExecutiveView
          summary={summary}
          isPartial={executive.status === 'ready' && executive.coverage === 'partial'}
        />
      )}

      {data ? (
        <DashboardSnapshotView snapshot={data} isPartial={isPartial} />
      ) : (
        <DashboardStateNotice
          status={snapshot.status as 'loading' | 'empty' | 'error' | 'forbidden' | 'unavailable'}
        />
      )}
    </>
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

      {/* The snapshot KPI strip that used to sit here is gone. It has been
          superseded by the executive KPI row above, which leads the page,
          and keeping both meant four headline figures appearing twice in
          one screenful.

          One of its four cards was also labelled "Compliance score" over a
          percentage. No backend computes a regulatory judgement, so the
          product cannot make one; that figure is now "Evidence readiness",
          which describes documents rather than law. `DashboardKpiCard` and
          its metric contract are untouched and still used elsewhere. */}

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
