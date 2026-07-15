import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  DemoDataBadge,
  EmptyState,
  Icon,
  LoadingSkeleton,
  Pagination,
  SectionCard,
} from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';
import { cn } from '@/lib/utils/cn';
import type { StringKey } from '@/lib/i18n/strings/en';
import { MOCK_ANALYSIS_RUNS, type AnalysisRunStatus } from '../mockAnalysisData';
import { AnalysisStatusBadge } from '../components/AnalysisStatusBadge';

const PAGE_SIZE = 5;

const STATUS_RAIL: Record<AnalysisRunStatus, string> = {
  COMPLETE: 'bg-leaf-500',
  PROCESSING: 'bg-sky-700',
  FAILED: 'bg-red-700',
  INSUFFICIENT_EVIDENCE: 'bg-amber-700',
};

const STATUS_DETAIL_KEY: Record<AnalysisRunStatus, StringKey> = {
  COMPLETE: 'analysis.kpi.completed.detail',
  PROCESSING: 'analysis.kpi.processing.detail',
  FAILED: 'analysis.kpi.failed.detail',
  INSUFFICIENT_EVIDENCE: 'analysis.kpi.insufficientEvidence.detail',
};

const TAB_VALUES = ['ALL', 'COMPLETE', 'PROCESSING', 'FAILED', 'INSUFFICIENT_EVIDENCE'] as const;
type TabValue = (typeof TAB_VALUES)[number];

const TAB_LABEL_KEY: Record<TabValue, StringKey> = {
  ALL: 'analysis.tabs.all',
  COMPLETE: 'analysis.status.complete',
  PROCESSING: 'analysis.status.processing',
  FAILED: 'analysis.status.failed',
  INSUFFICIENT_EVIDENCE: 'analysis.status.insufficientEvidence',
};

const ORGANIZATIONS = Array.from(new Set(MOCK_ANALYSIS_RUNS.map((run) => run.orgName)));

export function AnalysisListPage() {
  const { t } = useLocale();
  const { sessionKind } = useAuth();

  // Live mode: the backend does not yet provide a tenant-safe
  // analysis-runs list endpoint (deferred work), so this page shows a
  // truthful limited state instead of ever mixing mock rows into a live
  // session. Individual runs are reachable from their document page and
  // via /analysis/{runId}.
  if (sessionKind === 'live') {
    return (
      <div>
        <PageHeader
          eyebrow={t('analysis.eyebrow')}
          title={t('nav.analysis')}
          subtitle={t('analysis.live.subtitle')}
        />
        <SectionCard className="rounded-xl">
          <EmptyState
            title={t('analysis.live.noHistory.title')}
            description={t('analysis.live.noHistory.description')}
            action={
              <Link to="/documents" className="font-semibold text-leaf-700 hover:underline">
                {t('analysis.live.noHistory.action')}
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  return <DemoAnalysisList />;
}

/** Unchanged demo/preview rendering — the exact pre-live mock-data page,
 * preserved verbatim so the live branch above adds no risk to it. */
function DemoAnalysisList() {
  const { t } = useLocale();
  const [tab, setTab] = useState<TabValue>('ALL');
  const [search, setSearch] = useState('');
  const [org, setOrg] = useState<string>('ALL');
  const [page, setPage] = useState(1);

  const kpis = (['COMPLETE', 'PROCESSING', 'FAILED', 'INSUFFICIENT_EVIDENCE'] as AnalysisRunStatus[]).map(
    (status) => ({
      status,
      count: MOCK_ANALYSIS_RUNS.filter((run) => run.status === status).length,
    }),
  );

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return MOCK_ANALYSIS_RUNS.filter((run) => {
      if (tab !== 'ALL' && run.status !== tab) return false;
      if (org !== 'ALL' && run.orgName !== org) return false;
      if (
        query &&
        !run.analysisName.toLowerCase().includes(query) &&
        !run.documentName.toLowerCase().includes(query)
      ) {
        return false;
      }
      return true;
    });
  }, [tab, org, search]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageStart = (currentPage - 1) * PAGE_SIZE;
  const pageItems = filtered.slice(pageStart, pageStart + PAGE_SIZE);

  function updateFilter(next: Partial<{ tab: TabValue; org: string; search: string }>) {
    if (next.tab !== undefined) setTab(next.tab);
    if (next.org !== undefined) setOrg(next.org);
    if (next.search !== undefined) setSearch(next.search);
    setPage(1);
  }

  return (
    <div>
      <PageHeader
        eyebrow={t('analysis.eyebrow')}
        title={t('nav.analysis')}
        subtitle={t('analysis.subtitle')}
        action={<DemoDataBadge label={t('analysis.sampleBadge')} />}
      />

      <dl className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <AnalysisMetric
          icon="analysis"
          label={t('analysis.kpi.total')}
          value={String(MOCK_ANALYSIS_RUNS.length)}
          detail={t('analysis.kpi.total.detail')}
        />
        {kpis.map(({ status, count }) => (
          <AnalysisMetric
            key={status}
            icon={status === 'COMPLETE' ? 'check' : status === 'FAILED' ? 'triangle-alert' : 'analysis'}
            label={t(TAB_LABEL_KEY[status])}
            value={String(count)}
            detail={t(STATUS_DETAIL_KEY[status])}
          />
        ))}
      </dl>

      <SectionCard
        className="rounded-xl border-leaf-300/60"
        title={t('analysis.table.title')}
        description={t('analysis.table.description')}
        contentClassName="p-0 sm:p-0"
      >
        <div className="flex flex-col gap-3 border-b border-line-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="flex flex-wrap items-center gap-1" role="tablist" aria-label={t('analysis.table.title')}>
            {TAB_VALUES.map((value) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={tab === value}
                onClick={() => updateFilter({ tab: value })}
                className={cn(
                  'rounded-m px-3 py-1.5 text-caption font-bold transition-colors',
                  tab === value ? 'bg-forest-900 text-white' : 'text-gray-600 hover:bg-tint-100 hover:text-forest-900',
                )}
              >
                {t(TAB_LABEL_KEY[value])}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <div className="relative">
              <Icon
                name="search"
                size={15}
                className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-gray-400"
              />
              <input
                type="search"
                value={search}
                onChange={(event) => updateFilter({ search: event.target.value })}
                aria-label={t('analysis.search.label')}
                placeholder={t('analysis.search.placeholder')}
                className="h-9 w-full rounded-m border border-line-300 bg-surface-0 ps-9 pe-3 text-meta text-ink-900 outline-none transition-colors placeholder:text-gray-400 focus:border-forest-900 sm:w-56"
              />
            </div>
            <div className="relative">
              <Icon
                name="filter"
                size={14}
                className="pointer-events-none absolute start-2.5 top-1/2 -translate-y-1/2 text-gray-400"
              />
              <select
                value={org}
                onChange={(event) => updateFilter({ org: event.target.value })}
                aria-label={t('analysis.filter.label')}
                className="h-9 rounded-m border border-line-300 bg-surface-0 ps-8 pe-3 text-meta text-ink-900 outline-none transition-colors focus:border-forest-900"
              >
                <option value="ALL">{t('analysis.filter.allOrganizations')}</option>
                {ORGANIZATIONS.map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {pageItems.length === 0 ? (
          <p className="px-5 py-8 text-center text-meta text-gray-600">{t('analysis.empty.noResults')}</p>
        ) : (
          <ul className="space-y-3 p-3 sm:p-4" aria-label={t('analysis.table.title')}>
            {pageItems.map((run) => (
              <li key={run.id}>
                <Link
                  to={`/analysis/${run.id}`}
                  aria-label={t('analysis.viewAction', { name: run.analysisName })}
                  className={cn(
                    'surface-lift group relative grid gap-4 overflow-hidden rounded-xl border bg-surface-0 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center',
                    'border-line-200',
                  )}
                >
                  <span className={cn('absolute inset-y-2 start-0 w-1 rounded-e-full', STATUS_RAIL[run.status])} aria-hidden />
                  <span className="flex min-w-0 items-start gap-3">
                    <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-l border border-leaf-300 bg-mist-50 text-leaf-700" aria-hidden>
                      <Icon name="analysis" size={20} />
                    </span>
                    <span className="min-w-0">
                      <span className="type-label block text-gray-600">{run.analysisName}</span>
                      <span className="mt-0.5 block truncate text-body font-bold text-ink-900 transition-colors group-hover:text-leaf-700" data-user-content>
                        {run.documentName}
                      </span>
                      <span className="mt-1 block truncate text-caption text-gray-600" data-user-content>
                        {run.orgName} · {t('analysis.startedAt', { date: run.startedAt })}
                      </span>
                    </span>
                  </span>

                  <span className="flex min-w-40 flex-col items-start gap-2 sm:items-end">
                    <AnalysisStatusBadge status={run.status} />
                    {run.confidence != null && (
                      <span className="w-full sm:w-40">
                        <span className="flex items-center justify-between gap-2 text-caption font-semibold text-gray-600">
                          <span>{t('analysis.sampleConfidence')}</span>
                          <span>{run.confidence}%</span>
                        </span>
                        <progress
                          className="sr-only"
                          aria-label={`${run.documentName} ${t('analysis.sampleConfidence')}`}
                          max={100}
                          value={run.confidence}
                        >
                          {run.confidence}%
                        </progress>
                        <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-line-200" aria-hidden>
                          <span
                            className="block h-full rounded-full bg-leaf-500"
                            style={{ width: `${run.confidence}%` }}
                          />
                        </span>
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}

        <Pagination
          page={currentPage}
          pageCount={pageCount}
          onPageChange={setPage}
          summary={t('analysis.pagination.showing', {
            start: filtered.length === 0 ? 0 : pageStart + 1,
            end: Math.min(pageStart + PAGE_SIZE, filtered.length),
            total: filtered.length,
          })}
          previousLabel={t('analysis.pagination.previous')}
          nextLabel={t('analysis.pagination.next')}
        />
      </SectionCard>

      <section className="mt-5" aria-labelledby="analysis-state-preview-heading">
        <div className="mb-3">
          <p className="type-label text-leaf-700">{t('analysis.states.eyebrow')}</p>
          <h2 id="analysis-state-preview-heading" className="mt-1 text-panel text-forest-900">
            {t('analysis.states.title')}
          </h2>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <SectionCard className="rounded-xl bg-mist-50">
            <EmptyState
              title={t('analysis.states.noAnalysis.title')}
              description={t('analysis.states.noAnalysis.description')}
              className="py-5"
            />
          </SectionCard>
          <SectionCard className="rounded-xl border-leaf-300/60 bg-mist-50" aria-live="polite">
            <p className="mb-3 text-meta font-bold text-forest-900">{t('analysis.states.processing.label')}</p>
            <LoadingSkeleton lines={4} label={t('analysis.states.processing.description')} />
          </SectionCard>
          <SectionCard className="rounded-xl bg-tint-100">
            <EmptyState
              title={t('analysis.states.notAvailable.title')}
              description={t('analysis.states.notAvailable.description')}
              className="py-5"
            />
          </SectionCard>
        </div>
      </section>
    </div>
  );
}

function AnalysisMetric({
  icon,
  label,
  value,
  detail,
}: {
  icon: 'analysis' | 'check' | 'triangle-alert';
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="surface-lift flex items-center gap-3 rounded-xl border border-line-200 bg-surface-0 p-4 shadow-card">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-l bg-leaf-100 text-leaf-700">
        <Icon name={icon} size={19} />
      </span>
      <div className="min-w-0">
        <dt className="text-caption font-semibold text-gray-600">{label}</dt>
        <dd className="mt-0.5 text-title text-forest-900">{value}</dd>
        <dd className="truncate text-caption text-gray-600">{detail}</dd>
      </div>
    </div>
  );
}
