import { useState } from 'react';
import { Link } from 'react-router';
import {
  Button,
  DataTable,
  DataTableSkeleton,
  DemoDataBadge,
  Icon,
  Input,
  Pagination,
  PartialCoverageNotice,
  SectionCard,
  StateBlock,
  type DataTableColumn,
} from '@/design-system';
import { useOrganizationsList } from '@/lib/data/hooks/useOrganizationData';
import type { OrganizationSummary } from '@/lib/data/contracts';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { PageHeader } from '@/shell/PageHeader';

type Translate = ReturnType<typeof useLocale>['t'];

/** Built at module scope, not inside the component: these cell renderers
 * are render callbacks, not components, and defining them per render would
 * both churn identities and read as nested components. */
function organizationColumns(t: Translate): DataTableColumn<OrganizationSummary>[] {
  return [
    {
      id: 'name',
      header: t('organizations.table.column.name'),
      isRowHeader: true,
      cell: (organization) => (
        <Link
          to={`/organizations/${organization.id}`}
          aria-label={t('organizations.view', { name: organization.name })}
          className="rounded-s text-forest-900 underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
        >
          <span data-user-content>{organization.name}</span>
        </Link>
      ),
    },
    {
      id: 'created',
      header: t('organizations.table.column.created'),
      secondary: true,
      cell: (organization) =>
        organization.createdAt ? (
          <time dir="ltr">{formatDateTime(organization.createdAt)}</time>
        ) : (
          t('workspace.value.notRecorded')
        ),
    },
  ];
}

/**
 * The organizations listing.
 *
 * `GET /api/v1/organizations` returns the caller's own single organization
 * — the service reads their trusted `organization_id` and returns exactly
 * that row, with `total` fixed at 1. The client sends no parameters at all,
 * so there is nothing here a client-supplied value could influence.
 *
 * **There is no Live "Create organization" button**, and that is not an
 * oversight. `OrganizationService.create` raises
 * `AuthorizationError("Organization creation is not available in this
 * phase.")` unconditionally, for every role including Owner. A button here
 * could only ever produce a 403, so the page states plainly that creation
 * is not available through the product API, and why.
 *
 * Preview offers a clearly-labelled, non-persistent demonstration of the
 * form instead. It appends to component state, contacts nothing, and is
 * gone on reload — which its own notice says in as many words.
 *
 * Deletion is implemented in neither mode: the API exposes no delete route
 * for an organization.
 */
export function OrganizationsListPage() {
  const { t } = useLocale();
  const preview = isPreviewMode();
  const { state, retry } = useOrganizationsList();
  const columns = organizationColumns(t);

  const collection = state.status === 'ready' ? state.data : null;


  return (
    <div>
      <PageHeader
        eyebrow={t('organizations.eyebrow')}
        title={t('nav.organizations')}
        subtitle={preview ? t('organizations.preview.subtitle') : t('organizations.subtitle')}
        action={preview ? <DemoDataBadge label={t('dashboard.sampleData')} /> : undefined}
      />

      {state.status === 'ready' && state.coverage === 'partial' && (
        <PartialCoverageNotice message={t('workspace.state.partial')} />
      )}

      {collection ? (
        <SectionCard
          className="rounded-xl border-leaf-300/60"
          title={t('organizations.table.caption')}
          contentClassName="p-0 sm:p-0"
        >
          <DataTable
            caption={t('organizations.table.caption')}
            columns={columns}
            rows={collection.items}
            rowKey={(organization) => organization.id}
            emptyMessage={t('organizations.empty.title')}
          />
          <Pagination
            page={collection.page}
            pageCount={Math.max(1, Math.ceil(collection.total / Math.max(1, collection.pageSize)))}
            onPageChange={() => {}}
            summary={t('organizations.pagination.showing', {
              start: collection.total === 0 ? 0 : 1,
              end: collection.items.length,
              // The service's own count, carried through untouched.
              total: collection.total,
            })}
            previousLabel={t('organizations.pagination.previous')}
            nextLabel={t('organizations.pagination.next')}
          />
        </SectionCard>
      ) : (
        <SectionCard className="rounded-xl border-leaf-300/60">
          <StateBlock
            status={state.status === 'ready' ? 'error' : state.status}
            loadingLabel={t('workspace.state.loading')}
            loadingSkeleton={<DataTableSkeleton columns={2} rows={2} />}
            title={
              state.status === 'empty'
                ? t('organizations.empty.title')
                : state.status === 'forbidden'
                  ? t('workspace.state.forbidden.title')
                  : state.status === 'loading'
                    ? t('workspace.state.loading')
                    : t('organizations.error.title')
            }
            description={
              state.status === 'empty'
                ? t('organizations.empty.description')
                : state.status === 'forbidden'
                  ? t('workspace.state.forbidden.description')
                  : state.status === 'error'
                    ? t('workspace.state.error.description')
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
      )}

      <CreationDisclosure />
      {preview && <PreviewOnlyCreateForm />}
    </div>
  );
}

/** Shown in every mode, because in every mode it is true. */
function CreationDisclosure() {
  const { t } = useLocale();
  return (
    <SectionCard className="mt-5 border-dashed">
      <h2 className="text-panel text-forest-900">{t('organizations.create.unavailable.title')}</h2>
      <p className="mt-2 max-w-3xl text-body text-gray-600">
        {t('organizations.create.unavailable.description')}
      </p>
      <p className="mt-2 max-w-3xl text-meta text-gray-600">
        {t('organizations.delete.unavailable')}
      </p>
    </SectionCard>
  );
}

/**
 * A Preview-only demonstration of the create form.
 *
 * Renders only in a Preview build, is labelled as Preview in its own
 * heading, contacts nothing, and persists nothing — an added name lives in
 * this component's state until the page is reloaded. This module imports
 * no endpoint client, so there is nothing here it could reach.
 */
function PreviewOnlyCreateForm() {
  const { t } = useLocale();
  const [name, setName] = useState('');
  const [added, setAdded] = useState<string[]>([]);

  return (
    <SectionCard
      className="mt-5"
      title={t('organizations.preview.create.action')}
      description={t('organizations.preview.create.notice')}
    >
      <form
        className="flex flex-col gap-4 sm:flex-row sm:items-end"
        onSubmit={(event) => {
          event.preventDefault();
          const trimmed = name.trim();
          if (!trimmed) return;
          setAdded((current) => [...current, trimmed]);
          setName('');
        }}
      >
        <Input
          label={t('organizations.preview.create.label')}
          value={name}
          onChange={(event) => setName(event.target.value)}
          containerClassName="flex-1"
          maxLength={200}
        />
        <Button type="submit" disabled={name.trim().length === 0}>
          {t('organizations.preview.create.submit')}
        </Button>
      </form>

      {added.length > 0 && (
        <div className="mt-4">
          <output className="block text-meta text-gray-600">
            {t('organizations.preview.create.added')}
          </output>
          <ul className="mt-2 space-y-1">
            {added.map((entry, index) => (
              <li key={`${entry}-${index}`} className="text-body text-ink-900" data-user-content>
                {entry}
              </li>
            ))}
          </ul>
        </div>
      )}
    </SectionCard>
  );
}
