import { Link } from 'react-router';
import {
  Button,
  Icon,
  LoadingSkeleton,
  PartialCoverageNotice,
  SectionCard,
  StateBlock,
} from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { CountCard, UnavailableMetricCard } from '@/features/workspace/components/CountCard';
import { useDashboardLiveSummary } from '@/lib/data/hooks/useDashboardData';
import {
  LIVE_UNAVAILABLE_METRICS,
  type DocumentState,
  type LiveUnavailableMetric,
} from '@/lib/data/contracts';
import type { StringKey } from '@/lib/i18n/strings/en';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { DocumentStatusPip } from './StatusPip';

/**
 * The Live dashboard.
 *
 * Every number on this screen is a `total` the backend computed over the
 * caller's own tenant-scoped query. Nothing is derived from the rows that
 * happened to come back: the recent-documents request asks for five
 * documents and its `items` are used for exactly one thing — listing those
 * five — while the "Documents" figure beside them comes from the same
 * response's `total`, and each per-state figure comes from its own filtered
 * request's `total`.
 *
 * `null` never renders as `0`. A counter whose request failed shows the
 * word "Unavailable" and the sentence "This figure could not be loaded. It
 * is not zero." (see `CountCard`), because a workspace with no failed
 * documents and a workspace whose failure count could not be fetched are
 * different situations and a reader must be able to tell them apart.
 *
 * The four capabilities with no endpoint — evidence review, the activity
 * feed, reporting readiness, the processing queue — are named in compact
 * cards that say nothing provides them yet. They are not rendered as empty
 * lists, zeroed counters, placeholder charts, or a "coming soon" panel,
 * each of which would imply either a measurement or a commitment.
 *
 * There is no Preview import anywhere in this component's dependency
 * graph, so a Live failure has nothing synthetic to fall back to.
 */

const DOCUMENT_STATE_LABEL_KEY: Record<DocumentState, StringKey> = {
  pending: 'documents.status.pending',
  processing: 'documents.status.processing',
  processed: 'documents.status.processed',
  failed: 'documents.status.failed',
};

const DOCUMENT_STATES: readonly DocumentState[] = ['processed', 'processing', 'pending', 'failed'];

const UNAVAILABLE_LABEL_KEY: Record<LiveUnavailableMetric, StringKey> = {
  evidenceReview: 'dashboard.live.unavailable.evidenceReview',
  activity: 'dashboard.live.unavailable.activity',
  readiness: 'dashboard.live.unavailable.readiness',
  processingQueue: 'dashboard.live.unavailable.processingQueue',
};

export function DashboardLiveView() {
  const { t } = useLocale();
  const { state, retry } = useDashboardLiveSummary();

  if (state.status !== 'ready') {
    return (
      <div className="mt-4 flex flex-col gap-5 sm:mt-5">
        <SectionCard className="rounded-xl border-leaf-300/60">
          <StateBlock
            status={state.status}
            loadingLabel={t('workspace.state.loading')}
            loadingSkeleton={<LoadingSkeleton lines={6} label={t('workspace.state.loading')} />}
            title={
              state.status === 'empty'
                ? t('dashboard.live.empty.title')
                : state.status === 'forbidden'
                  ? t('workspace.state.forbidden.title')
                  : state.status === 'loading'
                    ? t('workspace.state.loading')
                    : state.status === 'unavailable'
                      ? t('dashboard.unavailable.title')
                      : t('dashboard.live.error.title')
            }
            description={
              state.status === 'empty'
                ? t('dashboard.live.empty.description')
                : state.status === 'forbidden'
                  ? t('workspace.state.forbidden.description')
                  : state.status === 'unavailable'
                    ? t('dashboard.unavailable.description')
                    : state.status === 'error'
                      ? t('dashboard.live.error.description')
                      : undefined
            }
            action={
              state.status === 'error' ? (
                <Button size="sm" variant="ghost" onClick={retry}>
                  <Icon name="refresh" size={14} />
                  {t('workspace.state.retry')}
                </Button>
              ) : undefined
            }
          />
        </SectionCard>
        {/* Rendered whether or not the figures loaded: which capabilities
          have no service behind them is a fact about the product, not a
          property of this request. A reader who just hit a network error
          still deserves to know that evidence review, the activity feed,
          readiness, and the queue are absent by design rather than absent
          because the load failed. */}
        <NotConnectedSection />
      </div>
    );
  }

  const summary = state.data;

  return (
    <div className="mt-4 flex flex-col gap-5 sm:mt-5">
      {state.coverage === 'partial' && (
        <PartialCoverageNotice message={t('workspace.state.partial')} />
      )}

      <section aria-labelledby="dashboard-live-totals">
        <h2 id="dashboard-live-totals" className="mb-3 text-panel text-forest-900">
          {t('dashboard.live.section.totals')}
        </h2>
        <div className="grid grid-cols-1 gap-3 min-[30rem]:grid-cols-2 xl:grid-cols-3">
          <CountCard
            label={t('dashboard.live.card.documentsTotal')}
            detail={t('dashboard.live.card.documentsTotal.detail')}
            value={summary.documentsTotal}
            icon="documents"
          />
          <CountCard
            label={t('dashboard.live.card.engagementsTotal')}
            detail={t('dashboard.live.card.engagementsTotal.detail')}
            value={summary.engagementsTotal}
            icon="engagements"
          />
          <div className="surface-lift flex items-start gap-3 rounded-xl border border-line-200 bg-surface-0 p-4 shadow-card">
            <span
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-l border border-leaf-300 bg-leaf-100 text-leaf-700"
              aria-hidden
            >
              <Icon name="organizations" size={20} />
            </span>
            <div className="min-w-0">
              <p className="text-caption font-semibold text-gray-600">
                {t('dashboard.live.card.organization')}
              </p>
              <p className="mt-0.5 truncate text-body font-bold text-ink-900" data-user-content>
                {summary.organizationName ?? t('workspace.value.unavailable')}
              </p>
              <p className="mt-0.5 text-caption text-gray-600">
                {summary.organizationName
                  ? t('dashboard.live.card.organization.detail')
                  : t('workspace.value.unavailable.detail')}
              </p>
            </div>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            to={ROUTES.documents}
            className="inline-flex min-h-10 items-center gap-2 rounded-m border border-line-200 px-4 text-meta font-semibold text-forest-900 transition-colors hover:bg-tint-100"
          >
            <Icon name="documents" size={15} />
            {t('dashboard.live.viewDocuments')}
          </Link>
          <Link
            to={ROUTES.engagements}
            className="inline-flex min-h-10 items-center gap-2 rounded-m border border-line-200 px-4 text-meta font-semibold text-forest-900 transition-colors hover:bg-tint-100"
          >
            <Icon name="engagements" size={15} />
            {t('dashboard.live.viewEngagements')}
          </Link>
        </div>
      </section>

      <section aria-labelledby="dashboard-live-processing">
        <h2 id="dashboard-live-processing" className="mb-1 text-panel text-forest-900">
          {t('dashboard.live.section.processing')}
        </h2>
        <p className="mb-3 max-w-3xl text-meta text-gray-600">
          {t('dashboard.live.processing.description')}
        </p>
        <div className="grid grid-cols-1 gap-3 min-[30rem]:grid-cols-2 xl:grid-cols-4">
          {DOCUMENT_STATES.map((documentState) => (
            <CountCard
              key={documentState}
              label={t(DOCUMENT_STATE_LABEL_KEY[documentState])}
              // Exact, per-state `total` from its own filtered request.
              value={summary.documentsByState[documentState]}
            />
          ))}
        </div>
      </section>

      <SectionCard
        title={t('dashboard.live.recentDocuments.title')}
        description={t('dashboard.live.recentDocuments.description')}
      >
        {summary.recentDocuments.length === 0 ? (
          <p className="text-meta text-gray-600">{t('dashboard.live.recentDocuments.empty')}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {summary.recentDocuments.map((document) => (
              <li key={document.id}>
                <Link
                  to={`/documents/${document.id}`}
                  className="flex flex-col gap-2 rounded-l border border-line-200 bg-paper-50 px-4 py-3 transition-colors hover:bg-mist-50 min-[30rem]:flex-row min-[30rem]:items-center min-[30rem]:justify-between"
                >
                  <span className="min-w-0">
                    <span
                      className="block truncate text-body font-bold text-ink-900"
                      data-user-content
                    >
                      {document.filename}
                    </span>
                    <span className="mt-0.5 block text-caption text-gray-600">
                      <time dir="ltr">{formatDateTime(document.createdAt)}</time>
                    </span>
                  </span>
                  <span className="shrink-0">
                    <DocumentStatusPip state={document.state} />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <NotConnectedSection />
    </div>
  );
}

/**
 * The four capabilities no existing FastAPI contract provides.
 *
 * Named individually and compactly, rather than hidden behind one generic
 * "not connected" panel: a reader learns exactly which four things are
 * absent, and each card says the figure is neither zero nor empty. Nothing
 * here depends on a response, so it renders in every state of the page.
 */
function NotConnectedSection() {
  const { t } = useLocale();
  return (
    <section aria-labelledby="dashboard-live-not-connected">
      <h2 id="dashboard-live-not-connected" className="mb-3 text-panel text-forest-900">
        {t('dashboard.live.section.notConnected')}
      </h2>
      <div className="grid grid-cols-1 gap-3 min-[30rem]:grid-cols-2">
        {LIVE_UNAVAILABLE_METRICS.map((metric) => (
          <UnavailableMetricCard key={metric} label={t(UNAVAILABLE_LABEL_KEY[metric])} />
        ))}
      </div>
    </section>
  );
}
