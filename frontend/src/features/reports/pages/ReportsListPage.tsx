import { useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  Button,
  DataTable,
  DataTableSkeleton,
  DemoDataBadge,
  FilterBar,
  FilterSearch,
  Icon,
  SectionCard,
  Select,
  StateBlock,
  type DataTableColumn,
} from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { useReportsWorkspace } from '@/lib/data/hooks/useExecutiveData';
import type { ReportFramework, ReportSummary, ReportTemplate, ReportsWorkspace } from '@/lib/data/contracts';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import { formatDateTime } from '@/lib/utils/formatDate';
import { PageHeader } from '@/shell/PageHeader';
import { ReadinessMeter, ReportStatusBadge } from '../components/ReportStatusBadge';

/**
 * Reports.
 *
 * **Preview** is a complete demonstration workspace: summary figures, a
 * filterable report list, templates, a non-persistent generate action, and
 * an export action that states plainly that no file is produced. It is
 * entirely local. There is no `fetch`, no `apiRequest`, and no Supabase
 * call in this page's dependency graph, and the source it reads asserts
 * Preview mode and throws if a Live build ever reaches it.
 *
 * **Live** renders a stated unavailable surface. This backend exposes no
 * reporting endpoint at all, so there is nothing to list. It deliberately
 * does not render an empty table: "0 reports" claims the workspace has
 * none, when the truth is that the product cannot tell. That is the same
 * distinction the dashboard draws between `null` and zero.
 *
 * Neither branch claims a report was filed, certified, assured, or
 * accepted by any authority, because none of that would be true.
 */

const FRAMEWORK_LABEL_KEY: Record<ReportFramework, StringKey> = {
  gri: 'reports.framework.gri',
  csrd: 'reports.framework.csrd',
  issb: 'reports.framework.issb',
  internal: 'reports.framework.internal',
};

type Translate = ReturnType<typeof useLocale>['t'];

function reportColumns(t: Translate): DataTableColumn<ReportSummary>[] {
  return [
    {
      id: 'name',
      header: t('reports.table.column.name'),
      isRowHeader: true,
      cell: (report) => (
        <Link
          to={`/reports/${report.id}`}
          className="rounded-s text-forest-900 underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
        >
          <span data-user-content>{report.name}</span>
        </Link>
      ),
    },
    {
      id: 'framework',
      header: t('reports.table.column.framework'),
      cell: (report) => t(FRAMEWORK_LABEL_KEY[report.framework]),
    },
    {
      id: 'status',
      header: t('reports.table.column.status'),
      cell: (report) => <ReportStatusBadge status={report.status} />,
    },
    {
      id: 'readiness',
      header: t('reports.table.column.readiness'),
      cell: (report) => <ReadinessMeter percent={report.readinessPercent} />,
    },
    {
      id: 'owner',
      header: t('reports.table.column.owner'),
      secondary: true,
      cell: (report) => <span data-user-content>{report.owner}</span>,
    },
    {
      id: 'updated',
      header: t('reports.table.column.updated'),
      secondary: true,
      cell: (report) => (
        <time dir="ltr" dateTime={report.updatedAt}>
          {formatDateTime(report.updatedAt)}
        </time>
      ),
    },
  ];
}

export function ReportsListPage() {
  const { t } = useLocale();
  const preview = isPreviewMode();
  const state = useReportsWorkspace();

  const [search, setSearch] = useState('');
  const [framework, setFramework] = useState('ALL');
  const [status, setStatus] = useState('ALL');
  const [notice, setNotice] = useState<string | null>(null);

  const workspace = state.status === 'ready' ? state.data : null;
  const columns = reportColumns(t);

  const rows = useMemo(() => {
    if (!workspace) return [];
    const query = search.trim().toLowerCase();
    return workspace.reports.filter((report) => {
      if (framework !== 'ALL' && report.framework !== framework) return false;
      if (status !== 'ALL' && report.status !== status) return false;
      if (query.length === 0) return true;
      return (
        report.name.toLowerCase().includes(query) || report.owner.toLowerCase().includes(query)
      );
    });
  }, [workspace, search, framework, status]);

  const filtered = search.trim().length > 0 || framework !== 'ALL' || status !== 'ALL';

  return (
    <div>
      <PageHeader
        eyebrow={t('reports.eyebrow')}
        title={t('nav.reports')}
        subtitle={preview ? t('reports.preview.subtitle') : t('reports.live.subtitle')}
        action={preview ? <DemoDataBadge label={t('dashboard.sampleData')} /> : undefined}
      />

      {workspace ? (
        <div className="flex flex-col gap-4 sm:gap-5">
          <ReportTotals workspace={workspace} />

          <SectionCard
            title={t('reports.table.caption')}
            description={t('reports.table.description', { period: workspace.reportingPeriod })}
            contentClassName="p-0 sm:p-0"
          >
            <FilterBar label={t('reports.filter.label')}>
              <FilterSearch
                label={t('reports.search.label')}
                placeholder={t('reports.search.placeholder')}
                value={search}
                onChange={setSearch}
              />
              <Select
                icon="filter"
                value={framework}
                onChange={(event) => setFramework(event.target.value)}
                aria-label={t('reports.filter.framework')}
                options={[
                  { value: 'ALL', label: t('reports.filter.allFrameworks') },
                  { value: 'gri', label: t('reports.framework.gri') },
                  { value: 'csrd', label: t('reports.framework.csrd') },
                  { value: 'issb', label: t('reports.framework.issb') },
                  { value: 'internal', label: t('reports.framework.internal') },
                ]}
              />
              <Select
                value={status}
                onChange={(event) => setStatus(event.target.value)}
                aria-label={t('reports.filter.status')}
                options={[
                  { value: 'ALL', label: t('reports.filter.allStatuses') },
                  { value: 'draft', label: t('reports.status.draft') },
                  { value: 'inReview', label: t('reports.status.inReview') },
                  { value: 'readyToPublish', label: t('reports.status.readyToPublish') },
                  { value: 'published', label: t('reports.status.published') },
                ]}
              />
            </FilterBar>

            <DataTable
              caption={t('reports.table.caption')}
              columns={columns}
              rows={rows}
              rowKey={(report) => report.id}
              emptyMessage={
                filtered ? t('reports.empty.noMatches') : t('reports.empty.description')
              }
            />
          </SectionCard>

          <ReportTemplates
            templates={workspace.templates}
            onDemonstrate={setNotice}
            notice={notice}
          />
        </div>
      ) : (
        <SectionCard>
          <StateBlock
            // `ready` is unreachable here (this branch runs only when
            // `workspace` is null), but the union still carries it.
            status={state.status === 'ready' ? 'error' : state.status}
            loadingLabel={t('workspace.state.loading')}
            loadingSkeleton={<DataTableSkeleton columns={4} />}
            title={
              state.status === 'unavailable'
                ? t('reports.unavailable.title')
                : state.status === 'forbidden'
                  ? t('workspace.state.forbidden.title')
                  : state.status === 'empty'
                    ? t('reports.empty.title')
                    : state.status === 'loading'
                      ? t('workspace.state.loading')
                      : t('workspace.state.error.title')
            }
            description={
              state.status === 'unavailable'
                ? t('reports.unavailable.description')
                : state.status === 'forbidden'
                  ? t('workspace.state.forbidden.description')
                  : state.status === 'empty'
                    ? t('reports.empty.description')
                    : state.status === 'error'
                      ? t('workspace.state.error.description')
                      : undefined
            }
            action={
              state.status === 'unavailable' ? (
                <Link
                  to={ROUTES.documents}
                  className="text-body font-semibold text-leaf-700 underline-offset-2 hover:underline"
                >
                  {t('nav.documents')}
                </Link>
              ) : undefined
            }
          />
        </SectionCard>
      )}
    </div>
  );
}

/** Four authored totals. None is `reports.length`: the same discipline the
 * Live dashboard is held to, so the two pages read alike. */
function ReportTotals({ workspace }: { workspace: ReportsWorkspace }) {
  const { t } = useLocale();

  const items: readonly { id: string; label: string; value: string }[] = [
    { id: 'all', label: t('reports.total.all'), value: String(workspace.totals.all) },
    {
      id: 'ready',
      label: t('reports.total.readyToPublish'),
      value: String(workspace.totals.readyToPublish),
    },
    {
      id: 'review',
      label: t('reports.total.inReview'),
      value: String(workspace.totals.inReview),
    },
    {
      id: 'readiness',
      label: t('reports.total.averageReadiness'),
      value: `${workspace.totals.averageReadinessPercent}%`,
    },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      {items.map((item) => (
        <div
          key={item.id}
          className="rounded-l border border-line-200 bg-surface-0 p-4 shadow-card"
        >
          <dt className="text-caption font-bold uppercase tracking-wide text-gray-600">
            {item.label}
          </dt>
          <dd className="mt-1.5 text-display font-bold leading-none text-forest-900" dir="ltr">
            {item.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/**
 * Templates, plus the two demonstration actions.
 *
 * Both are explicitly non-persistent. "Generate preview" sets a local
 * string; "Export" sets a local string. Neither writes a file, starts a
 * download, or issues a request, and the copy says so rather than leaving
 * a reviewer to discover it. Reloading the page clears both, because the
 * only state involved is a `useState` in this component.
 */
function ReportTemplates({
  templates,
  onDemonstrate,
  notice,
}: {
  templates: readonly ReportTemplate[];
  onDemonstrate: (message: string) => void;
  notice: string | null;
}) {
  const { t } = useLocale();

  return (
    <SectionCard
      title={t('reports.templates.title')}
      description={t('reports.templates.description')}
    >
      <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {templates.map((template) => (
          <li
            key={template.id}
            className="flex min-w-0 flex-col gap-2 rounded-m border border-line-200 bg-tint-100/50 p-4"
          >
            <div className="flex flex-wrap items-center gap-2">
              <Icon name="reports" size={16} className="text-forest-900" />
              <h3 className="text-body font-bold text-forest-900">
                {t(template.nameKey as StringKey)}
              </h3>
            </div>
            <p className="text-caption text-gray-600">
              {t(template.descriptionKey as StringKey)}
            </p>
            <p className="text-caption text-gray-600">
              {t('reports.templates.sections', { count: template.sectionCount })}
            </p>
            <div className="mt-1 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onDemonstrate(t('reports.generate.notice'))}
              >
                {t('reports.generate.action')}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onDemonstrate(t('reports.export.notice'))}
              >
                {t('reports.export.action')}
              </Button>
            </div>
          </li>
        ))}
      </ul>

      {notice && (
        <output className="mt-4 block rounded-m border border-dashed border-line-300 bg-tint-100 px-4 py-3 text-meta text-gray-600">
          {notice}
        </output>
      )}
    </SectionCard>
  );
}
