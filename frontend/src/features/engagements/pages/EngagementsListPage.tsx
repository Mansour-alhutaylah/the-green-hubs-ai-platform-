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
  Pagination,
  PartialCoverageNotice,
  SectionCard,
  Select,
  StateBlock,
  type DataTableColumn,
} from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { RequireTier } from '@/features/rbac/RequireTier';
import { Role } from '@/features/rbac/roles';
import { useEngagementsList } from '@/lib/data/hooks/useEngagementData';
import type { EngagementSummary } from '@/lib/data/contracts';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { PageHeader } from '@/shell/PageHeader';
import { EngagementStatusBadge } from '../components/EngagementStatusBadge';
import { EngagementCreateForm } from '../components/EngagementCreateForm';

const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const DEFAULT_PAGE_SIZE = 20;

type Translate = ReturnType<typeof useLocale>['t'];

/** Built at module scope, not inside the component: these cell renderers
 * are render callbacks, not components, and defining them per render would
 * both churn identities and read as nested component definitions. */
function engagementColumns(t: Translate): DataTableColumn<EngagementSummary>[] {
  return [
    {
      id: 'title',
      header: t('engagements.table.column.title'),
      isRowHeader: true,
      cell: (engagement) => (
        <Link
          to={`/engagements/${engagement.id}`}
          aria-label={t('engagements.view', { name: engagement.title })}
          className="rounded-s text-forest-900 underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
        >
          <span data-user-content>{engagement.title}</span>
        </Link>
      ),
    },
    {
      id: 'status',
      header: t('engagements.table.column.status'),
      cell: (engagement) => <EngagementStatusBadge status={engagement.status} />,
    },
    {
      id: 'created',
      header: t('engagements.table.column.created'),
      secondary: true,
      cell: (engagement) =>
        engagement.createdAt ? (
          <time dir="ltr">{formatDateTime(engagement.createdAt)}</time>
        ) : (
          t('workspace.value.notRecorded')
        ),
    },
  ];
}

/**
 * The engagements listing.
 *
 * Pagination is genuinely server-side: `page` and `page_size` are the two
 * parameters `GET /api/v1/engagements` accepts, and the row count comes
 * from the `total` the service computes with its own tenant-scoped
 * `count()` — never from `items.length`, which is only ever the size of
 * the page in hand.
 *
 * `organization_id` is *not* sent. The route accepts it as an optional
 * filter, but tenant scope is the server's decision, derived from the
 * bearer token; a client-chosen id could only narrow a scope already
 * decided while making the request look like an assertion of tenancy.
 *
 * The search and status controls appear only when the loaded page holds
 * the entire collection. The service offers no search or status parameter,
 * so filtering client-side across a paginated set would report "no
 * matches" for a term that plainly matches rows on another page. When the
 * whole collection is in hand the filter is exact, and when it is not the
 * control is absent rather than misleading.
 */
export function EngagementsListPage() {
  const { t } = useLocale();
  const preview = isPreviewMode();

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(DEFAULT_PAGE_SIZE);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('ALL');
  const [creating, setCreating] = useState(false);

  const { state, retry } = useEngagementsList({ page, pageSize });
  const columns = engagementColumns(t);

  const collection = state.status === 'ready' ? state.data : null;
  const isComplete = collection != null && collection.items.length === collection.total;

  const visibleRows = useMemo(() => {
    if (!collection) return [];
    if (!isComplete) return collection.items;
    const query = search.trim().toLowerCase();
    return collection.items.filter((engagement) => {
      if (status !== 'ALL' && (engagement.status ?? '').trim().toLowerCase() !== status) {
        return false;
      }
      return query.length === 0 || engagement.title.toLowerCase().includes(query);
    });
  }, [collection, isComplete, search, status]);


  const pageCount = Math.max(1, Math.ceil((collection?.total ?? 0) / pageSize));
  const pageStart = (page - 1) * pageSize;

  return (
    <div>
      <PageHeader
        eyebrow={t('engagements.eyebrow')}
        title={t('nav.engagements')}
        subtitle={preview ? t('engagements.preview.subtitle') : t('engagements.subtitle')}
        action={
          <>
            {preview && <DemoDataBadge label={t('dashboard.sampleData')} />}
            {/*
              `engagement.manage` is granted to editor and above by the
              backend's own role policy, so a Viewer never sees this
              control — hidden rather than disabled, because a button that
              is guaranteed to be refused is not an affordance.
            */}
            <RequireTier minTier={Role.Editor}>
              <Button size="md" onClick={() => setCreating((open) => !open)} aria-expanded={creating}>
                <Icon name="upload" size={16} />
                {t('engagements.create.action')}
              </Button>
            </RequireTier>
          </>
        }
      />

      <RequireTier minTier={Role.Editor}>
        {creating && (
          <EngagementCreateForm
            className="mb-5"
            onCancel={() => setCreating(false)}
            onCreated={() => {
              setCreating(false);
              setPage(1);
              retry();
            }}
          />
        )}
      </RequireTier>

      {state.status === 'ready' && state.coverage === 'partial' && (
        <PartialCoverageNotice message={t('workspace.state.partial')} />
      )}

      {state.status === 'ready' ? (
        <SectionCard
          className="rounded-xl border-leaf-300/60"
          title={t('engagements.table.caption')}
          description={preview ? t('engagements.preview.subtitle') : t('engagements.subtitle')}
          contentClassName="p-0 sm:p-0"
        >
          <FilterBar label={t('engagements.filter.label')}>
            {isComplete && (
              <>
                <FilterSearch
                  label={t('engagements.search.label')}
                  placeholder={t('engagements.search.placeholder')}
                  value={search}
                  onChange={setSearch}
                />
                <Select
                  icon="filter"
                  value={status}
                  onChange={(event) => setStatus(event.target.value)}
                  aria-label={t('engagements.filter.status')}
                  options={[
                    { value: 'ALL', label: t('engagements.filter.allStatuses') },
                    { value: 'active', label: t('engagements.status.active') },
                    { value: 'draft', label: t('engagements.status.draft') },
                    { value: 'closed', label: t('engagements.status.closed') },
                    { value: 'archived', label: t('engagements.status.archived') },
                  ]}
                />
              </>
            )}
            <Select
              value={String(pageSize)}
              onChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(1);
              }}
              aria-label={t('engagements.pagination.showing', {
                start: pageStart + 1,
                end: Math.min(pageStart + pageSize, collection?.total ?? 0),
                total: collection?.total ?? 0,
              })}
              options={PAGE_SIZE_OPTIONS.map((size) => ({
                value: String(size),
                label: String(size),
              }))}
            />
          </FilterBar>

          <DataTable
            caption={t('engagements.table.caption')}
            columns={columns}
            rows={visibleRows}
            rowKey={(engagement) => engagement.id}
            emptyMessage={t('engagements.empty.noResults')}
          />

          <Pagination
            page={page}
            pageCount={pageCount}
            onPageChange={setPage}
            summary={t('engagements.pagination.showing', {
              start: (collection?.total ?? 0) === 0 ? 0 : pageStart + 1,
              end: Math.min(pageStart + pageSize, collection?.total ?? 0),
              // The service's own count for the whole query.
              total: collection?.total ?? 0,
            })}
            previousLabel={t('engagements.pagination.previous')}
            nextLabel={t('engagements.pagination.next')}
          />
        </SectionCard>
      ) : (
        <SectionCard className="rounded-xl border-leaf-300/60">
          <StateBlock
            status={state.status === 'unavailable' ? 'unavailable' : state.status}
            loadingLabel={t('workspace.state.loading')}
            loadingSkeleton={<DataTableSkeleton columns={3} />}
            title={stateTitle(state.status, t)}
            description={stateDescription(state.status, t)}
            action={
              state.status === 'error' ? (
                <Button size="sm" variant="ghost" onClick={retry}>
                  <Icon name="refresh" size={14} />
                  {t('workspace.state.retry')}
                </Button>
              ) : state.status === 'empty' ? (
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

function stateTitle(status: string, t: Translate): string {
  if (status === 'empty') return t('engagements.empty.title');
  if (status === 'forbidden') return t('workspace.state.forbidden.title');
  if (status === 'error') return t('engagements.error.title');
  if (status === 'loading') return t('workspace.state.loading');
  return t('workspace.state.error.title');
}

function stateDescription(status: string, t: Translate): string | undefined {
  if (status === 'empty') return t('engagements.empty.description');
  if (status === 'forbidden') return t('workspace.state.forbidden.description');
  if (status === 'error') return t('workspace.state.error.description');
  return undefined;
}
