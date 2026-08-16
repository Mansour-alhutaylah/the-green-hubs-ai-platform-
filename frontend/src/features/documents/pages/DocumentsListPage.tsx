import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router';
import {
  Button,
  DemoDataBadge,
  Icon,
  Pagination,
  SectionCard,
  Select,
  TabPanel,
  Tabs,
  type IconName,
} from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { useEngagements } from '@/features/engagements/useEngagements';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { PageHeader } from '@/shell/PageHeader';
import { ROUTES } from '@/app/navigation/routePaths';
import { cn } from '@/lib/utils/cn';
import type { StringKey } from '@/lib/i18n/strings/en';
import { MOCK_DOCUMENTS, type DocumentProcessingStatus } from '../mockDocuments';
import { DocumentStatusBadge } from '../components/DocumentStatusBadge';
import { DocumentCollectionState, type DocumentCollectionView } from '../components/DocumentCollectionState';
import { useDocumentsQuery } from '../useDocumentsQuery';

const PAGE_SIZE = 5;

const countStatus = (status: DocumentProcessingStatus) =>
  MOCK_DOCUMENTS.filter((document) => document.status === status).length;

const STATUS_RAIL: Record<DocumentProcessingStatus, string> = {
  PENDING: 'bg-gray-400',
  PROCESSING: 'bg-sky-700',
  PROCESSED: 'bg-leaf-500',
  FAILED: 'bg-red-700',
};

const STATUS_CONTEXT_KEY: Record<DocumentProcessingStatus, StringKey> = {
  PENDING: 'documents.status.context.pending',
  PROCESSING: 'documents.status.context.processing',
  PROCESSED: 'documents.status.context.processed',
  FAILED: 'documents.status.context.failed',
};

const LIVE_STATUS_CONTEXT_KEY: Record<DocumentProcessingStatus, StringKey> = {
  PENDING: 'documents.status.context.live.pending',
  PROCESSING: 'documents.status.context.live.processing',
  PROCESSED: 'documents.status.context.live.processed',
  FAILED: 'documents.status.context.live.failed',
};

const TAB_VALUES = ['ALL', 'PENDING', 'PROCESSING', 'PROCESSED', 'FAILED'] as const;
type TabValue = (typeof TAB_VALUES)[number];

const TAB_LABEL_KEY: Record<TabValue, StringKey> = {
  ALL: 'documents.tabs.all',
  PENDING: 'documents.status.pending',
  PROCESSING: 'documents.status.processing',
  PROCESSED: 'documents.status.processed',
  FAILED: 'documents.status.failed',
};

const DEMO_ENGAGEMENT_NAMES = Array.from(new Set(MOCK_DOCUMENTS.map((document) => document.engagement)));

const TABS_ID = 'documents-status-filter';
const PANEL_ID = 'documents-results';

interface DocumentRow {
  id: string;
  name: string;
  engagementLabel: string;
  status: DocumentProcessingStatus;
  uploadedAtDisplay: string;
  uploadedAtDir?: 'ltr';
  secondaryLine: string;
}

export function DocumentsListPage() {
  const { t } = useLocale();
  const { sessionKind } = useAuth();
  const isLive = sessionKind === 'live';

  const [tab, setTab] = useState<TabValue>('ALL');
  const [search, setSearch] = useState('');
  const [engagementFilter, setEngagementFilter] = useState<string>('ALL');
  const [page, setPage] = useState(1);

  const engagementsState = useEngagements();
  const engagementTitleById = useMemo(
    () => new Map(engagementsState.engagements.map((item) => [item.id, item.title])),
    [engagementsState.engagements],
  );

  const documentsQuery = useDocumentsQuery(isLive, {
    engagementId: engagementFilter !== 'ALL' ? engagementFilter : undefined,
    processingStatus: tab !== 'ALL' ? tab : undefined,
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  });

  function updateFilter(next: Partial<{ tab: TabValue; engagement: string; search: string }>) {
    if (next.tab !== undefined) setTab(next.tab);
    if (next.engagement !== undefined) setEngagementFilter(next.engagement);
    if (next.search !== undefined) setSearch(next.search);
    setPage(1);
  }

  // --- Demo path: unchanged client-side filter/paginate over the fixture list. ---
  const demoFiltered = useMemo(() => {
    const query = search.trim().toLowerCase();
    return MOCK_DOCUMENTS.filter((document) => {
      if (tab !== 'ALL' && document.status !== tab) return false;
      if (engagementFilter !== 'ALL' && document.engagement !== engagementFilter) return false;
      if (query && !document.name.toLowerCase().includes(query)) return false;
      return true;
    });
  }, [tab, engagementFilter, search]);

  const engagementOptions = isLive
    ? engagementsState.engagements.map((item) => ({ value: item.id, label: item.title }))
    : DEMO_ENGAGEMENT_NAMES.map((name) => ({ value: name, label: name }));

  const total = isLive ? documentsQuery.total : demoFiltered.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const pageStart = (currentPage - 1) * PAGE_SIZE;

  /**
   * Live pagination is server-side, so an offset past the end of a
   * *shrunk* result set returns an empty page while earlier pages still
   * hold rows — the user is stranded on "no results" for a filter that
   * plainly has some. That happens whenever the total drops beneath the
   * current offset: a document is deleted, processing moves a row out of
   * the active status filter, or another session removes rows.
   *
   * Clamping `currentPage` above fixes what is *displayed*; this syncs the
   * page state that feeds the request, so the next fetch asks for a valid
   * offset. It runs only on a settled (`ready`) response, and only when the
   * page is genuinely out of range — after it fires once, `page <= maxPage`
   * holds, so it cannot loop or issue duplicate requests. Filter changes
   * already reset to page 1 through `updateFilter`.
   */
  useEffect(() => {
    if (!isLive || documentsQuery.status !== 'ready') return;
    const maxPage = Math.max(1, Math.ceil(documentsQuery.total / PAGE_SIZE));
    setPage((current) => (current > maxPage ? maxPage : current));
  }, [isLive, documentsQuery.status, documentsQuery.total]);

  const rows: DocumentRow[] = isLive
    ? documentsQuery.items.map((document) => {
        const status = document.processing_status as DocumentProcessingStatus;
        return {
          id: document.id,
          name: document.filename,
          engagementLabel: engagementTitleById.get(document.engagement_id) ?? document.engagement_id,
          status,
          uploadedAtDisplay: formatDateTime(document.created_at),
          uploadedAtDir: 'ltr',
          secondaryLine: document.has_extracted_text
            ? t('documents.live.chunkCount', { count: document.chunk_count })
            : t(LIVE_STATUS_CONTEXT_KEY[status]),
        };
      })
    : demoFiltered.slice(pageStart, pageStart + PAGE_SIZE).map((document) => ({
        id: document.id,
        name: document.name,
        engagementLabel: document.engagement,
        status: document.status,
        uploadedAtDisplay: document.uploadedAt,
        secondaryLine: `${document.size} · ${document.owner}`,
      }));

  const hasNoEngagements =
    isLive && engagementsState.status === 'ready' && engagementsState.engagements.length === 0;

  let collectionState: DocumentCollectionView = 'ready';
  if (isLive) {
    if (documentsQuery.status === 'loading' || engagementsState.status === 'loading') {
      collectionState = 'loading';
    } else if (documentsQuery.status === 'error') {
      collectionState = 'error';
    } else if (total === 0) {
      collectionState = 'empty';
    }
  }

  const summary: Array<{ label: string; value: number; detail: string; icon: IconName; className: string }> = [
    {
      label: t('documents.summary.total'),
      value: MOCK_DOCUMENTS.length,
      detail: t('documents.summary.total.detail'),
      icon: 'documents',
      className: 'border-leaf-300 bg-mist-50 text-forest-800',
    },
    {
      label: t('documents.summary.processed'),
      value: countStatus('PROCESSED'),
      detail: t('documents.summary.processed.detail'),
      icon: 'check',
      className: 'border-leaf-300 bg-leaf-100 text-leaf-700',
    },
    {
      label: t('documents.summary.inProgress'),
      value: countStatus('PROCESSING') + countStatus('PENDING'),
      detail: t('documents.summary.inProgress.detail'),
      icon: 'analysis',
      className: 'border-sky-100 bg-sky-100 text-sky-700',
    },
    {
      label: t('documents.summary.needsAttention'),
      value: countStatus('FAILED'),
      detail: t('documents.summary.needsAttention.detail'),
      icon: 'triangle-alert',
      className: 'border-amber-100 bg-amber-100 text-amber-700',
    },
  ];

  return (
    <div>
      <PageHeader
        eyebrow={t('documents.eyebrow')}
        title={t('nav.documents')}
        subtitle={isLive ? t('documents.live.subtitle') : t('documents.subtitle')}
        action={
          <>
            {!isLive && <DemoDataBadge label={t('dashboard.sampleData')} />}
            <Link
              to={ROUTES.documentUpload}
              className="inline-flex min-h-10 items-center gap-2 rounded-m bg-forest-900 px-4 text-body font-semibold text-white shadow-raise transition-colors hover:bg-forest-800 active:scale-[var(--scale-press)]"
            >
              <Icon name="upload" size={17} />
              {isLive ? t('nav.upload') : t('documents.uploadPreview')}
            </Link>
          </>
        }
      />

      {!isLive && (
        <dl className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 min-[1380px]:grid-cols-4">
          {summary.map((item) => (
            <div
              key={item.label}
              className="surface-lift flex items-center gap-3 rounded-xl border border-line-200 bg-surface-0 p-4 shadow-card"
            >
              <span className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-l border', item.className)}>
                <Icon name={item.icon} size={20} />
              </span>
              <div className="min-w-0">
                <dt className="text-caption font-semibold text-gray-600">{item.label}</dt>
                <dd className="mt-0.5 flex items-baseline gap-2">
                  <span className="text-title text-forest-900">{item.value}</span>
                  <span className="truncate text-caption text-gray-600">{item.detail}</span>
                </dd>
              </div>
            </div>
          ))}
        </dl>
      )}

      <DocumentCollectionState
        state={collectionState}
        emptyTitle={
          hasNoEngagements ? t('documents.live.empty.noEngagements.title') : t('documents.live.empty.noDocuments.title')
        }
        emptyDescription={
          hasNoEngagements
            ? t('documents.live.empty.noEngagements.description')
            : t('documents.live.empty.noDocuments.description')
        }
        errorTitle={t('documents.live.error.title')}
        errorDescription={documentsQuery.error ?? undefined}
        errorAction={
          <Button size="sm" variant="ghost" onClick={documentsQuery.retry}>
            <Icon name="refresh" size={14} />
            {t('documents.retry')}
          </Button>
        }
      >
        <SectionCard
          className="mt-5 rounded-xl border-leaf-300/60"
          title={t('documents.table.title')}
          description={isLive ? t('documents.live.table.description') : t('documents.table.description')}
          contentClassName="p-0 sm:p-0"
        >
          <div className="flex flex-col gap-3 border-b border-line-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
            <Tabs<TabValue>
              id={TABS_ID}
              panelId={PANEL_ID}
              label={t('documents.table.title')}
              value={tab}
              onChange={(value) => updateFilter({ tab: value })}
              items={TAB_VALUES.map((value) => ({ value, label: t(TAB_LABEL_KEY[value]) }))}
            />

            <div className="flex items-center gap-2">
              {!isLive && (
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
                    aria-label={t('documents.search.label')}
                    placeholder={t('documents.search.placeholder')}
                    className="h-9 w-full rounded-m border border-line-300 bg-surface-0 ps-9 pe-3 text-meta text-ink-900 outline-none transition-colors placeholder:text-gray-400 focus:border-forest-900 sm:w-56"
                  />
                </div>
              )}
              <Select
                icon="filter"
                value={engagementFilter}
                onChange={(event) => updateFilter({ engagement: event.target.value })}
                aria-label={t('documents.filter.label')}
                options={[
                  { value: 'ALL', label: t('documents.filter.allEngagements') },
                  ...engagementOptions,
                ]}
              />
            </div>
          </div>

          <TabPanel id={PANEL_ID} tabsId={TABS_ID} value={tab}>
          <div className="hidden grid-cols-[minmax(0,1.8fr)_minmax(10rem,1fr)_9rem_9rem_2.5rem] gap-4 border-b border-line-200 bg-mist-50 px-5 py-3 text-caption font-bold text-gray-600 md:grid">
            <span>{t('documents.table.column.document')}</span>
            <span>{t('documents.table.column.engagement')}</span>
            <span>{t('documents.table.column.status')}</span>
            <span>{t('documents.table.column.uploaded')}</span>
            <span aria-hidden />
          </div>

          {rows.length === 0 ? (
            <p className="px-5 py-8 text-center text-meta text-gray-600">{t('documents.empty.noResults')}</p>
          ) : (
            <ul className="divide-y divide-line-200" aria-label={t('documents.table.title')}>
              {rows.map((document) => (
                <li key={document.id}>
                  <Link
                    to={`/documents/${document.id}`}
                    aria-label={t('documents.viewAction', { name: document.name })}
                    className="group relative grid gap-3 overflow-hidden px-4 py-4 transition-colors hover:bg-mist-50 sm:px-5 md:grid-cols-[minmax(0,1.8fr)_minmax(10rem,1fr)_9rem_9rem_2.5rem] md:items-center md:gap-4"
                  >
                    <span className={cn('absolute inset-y-2 start-0 w-1 rounded-e-full', STATUS_RAIL[document.status])} aria-hidden />
                    <span className="flex min-w-0 items-start gap-3">
                      <span className="relative mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-l border border-leaf-300 bg-leaf-100 text-leaf-700 shadow-card" aria-hidden>
                        <Icon name="documents" size={20} />
                        <span className="absolute -bottom-1 -end-1 rounded-s bg-forest-900 px-1 py-0.5 text-micro font-bold text-white">PDF</span>
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-body font-bold text-ink-900 transition-colors group-hover:text-leaf-700" data-user-content>
                          {document.name}
                        </span>
                        <span className="mt-0.5 block text-caption text-gray-600">
                          {document.secondaryLine}
                        </span>
                        {!isLive && (
                          <span className="mt-1 block text-caption font-medium text-gray-600 md:hidden">
                            {t(STATUS_CONTEXT_KEY[document.status])}
                          </span>
                        )}
                      </span>
                    </span>
                    <span className="min-w-0">
                      <span className="type-label mb-1 block text-gray-600 md:hidden">{t('documents.table.column.engagement')}</span>
                      <span className="block truncate text-meta text-gray-600" data-user-content>
                        {document.engagementLabel}
                      </span>
                    </span>
                    <span>
                      <DocumentStatusBadge status={document.status} />
                    </span>
                    <span>
                      <span className="type-label mb-1 block text-gray-600 md:hidden">{t('documents.table.column.uploaded')}</span>
                      <time className="text-caption text-gray-600" dir={document.uploadedAtDir}>
                        {document.uploadedAtDisplay}
                      </time>
                    </span>
                    <span className="hidden items-center justify-end text-gray-400 transition-colors group-hover:text-leaf-700 md:flex" aria-hidden>
                      <Icon name="chevron-right" size={16} />
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
            summary={t('documents.pagination.showing', {
              start: total === 0 ? 0 : pageStart + 1,
              end: Math.min(pageStart + PAGE_SIZE, total),
              total,
            })}
            previousLabel={t('documents.pagination.previous')}
            nextLabel={t('documents.pagination.next')}
          />
          </TabPanel>
        </SectionCard>
      </DocumentCollectionState>
    </div>
  );
}
