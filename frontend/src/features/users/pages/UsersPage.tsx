import { useMemo, useState } from 'react';
import {
  Avatar,
  Badge,
  Button,
  DataTable,
  DataTableSkeleton,
  DemoDataBadge,
  FilterBar,
  FilterSearch,
  Icon,
  PartialCoverageNotice,
  RoleBadge,
  SectionCard,
  Select,
  StateBlock,
  type DataTableColumn,
} from '@/design-system';
import { Role, ROLE_LABELS } from '@/features/rbac/roles';
import { useTeamDirectory } from '@/lib/data/hooks/useTeamData';
import type { TeamMember } from '@/lib/data/contracts';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';

type Translate = ReturnType<typeof useLocale>['t'];

/** Built at module scope, not inside the component: these cell renderers
 * are render callbacks, not components, and defining them per render would
 * both churn identities and read as nested component definitions. */
function teamColumns(t: Translate): DataTableColumn<TeamMember>[] {
  return [
    {
      id: 'name',
      header: t('users.table.column.name'),
      isRowHeader: true,
      cell: (member) => (
        <span className="flex items-center gap-3">
          <Avatar name={member.fullName} size={32} />
          <span className="min-w-0">
            <span className="block truncate" data-user-content>
              {member.fullName}
            </span>
            {member.isCurrentUser && (
              <Badge className="mt-1 border-leaf-300 bg-leaf-100 text-leaf-700">
                {t('users.you')}
              </Badge>
            )}
          </span>
        </span>
      ),
    },
    {
      id: 'email',
      header: t('users.table.column.email'),
      secondary: true,
      cell: (member) => (
        <span className="break-all" dir="ltr" data-user-content>
          {member.email}
        </span>
      ),
    },
    {
      id: 'role',
      header: t('users.table.column.role'),
      cell: (member) =>
        member.role ? (
          <RoleBadge role={member.role} />
        ) : (
          // `users.role` is a free-form nullable column, and the backend
          // denies every permission for a value outside its enum. Naming
          // that is more useful than defaulting to a tier the server does
          // not actually grant.
          <span className="text-meta font-bold text-amber-700" title={t('users.role.unrecognized.detail')}>
            {t('users.role.unrecognized')}
          </span>
        ),
    },
  ];
}

/**
 * Users & Roles. Admin+ route (the router's `RoleGuard` covers it).
 *
 * **Live shows exactly one person: you.** There is no organization-wide
 * user endpoint on this backend, and its own permission catalogue says so
 * outright — "There is no `user.manage` permission because no
 * user-management route exists yet". The only real identity the product can
 * obtain is `GET /api/v1/auth/me`, so that is the only row, and the page
 * states why rather than implying a directory it cannot fetch.
 *
 * Deliberately absent from Live, because each would be theatre: an invite
 * control, a role-change control, a remove control, a seat count, a "last
 * active" column, a pending-invitations list. None has an endpoint. Each
 * would either do nothing or misrepresent what it did.
 *
 * Nothing here touches Supabase. No table read, no Admin API call, no
 * service-role credential — the browser client holds the public anon key
 * and is used for the bearer token alone. Enumerating `auth.users` from a
 * browser is exactly the shortcut this page refuses to take.
 *
 * Preview renders one obviously synthetic member per canonical role, so the
 * full tier model is reviewable, under a heading that says it is invented.
 */
export function UsersPage() {
  const { t } = useLocale();
  const preview = isPreviewMode();
  const { state, retry } = useTeamDirectory();
  const columns = teamColumns(t);

  const [search, setSearch] = useState('');
  const [role, setRole] = useState('ALL');

  const directory = state.status === 'ready' ? state.data : null;

  // Filtering is offered only when the directory in hand is the complete
  // set. In Live it never is — one row is not a directory — so the controls
  // do not appear rather than filtering a list that is already partial.
  const filterable = directory?.isCompleteDirectory === true;

  const rows = useMemo(() => {
    if (!directory) return [];
    if (!filterable) return directory.members;
    const query = search.trim().toLowerCase();
    return directory.members.filter((member) => {
      if (role !== 'ALL' && member.role !== role) return false;
      if (query.length === 0) return true;
      return (
        member.fullName.toLowerCase().includes(query) ||
        member.email.toLowerCase().includes(query)
      );
    });
  }, [directory, filterable, search, role]);


  return (
    <div>
      <PageHeader
        eyebrow={t('users.eyebrow')}
        title={t('nav.users')}
        subtitle={preview ? t('users.preview.subtitle') : t('users.subtitle')}
        action={preview ? <DemoDataBadge label={t('dashboard.sampleData')} /> : undefined}
      />

      {state.status === 'ready' && state.coverage === 'partial' && (
        <PartialCoverageNotice message={t('workspace.state.partial')} />
      )}

      <SectionCard
        className="rounded-xl border-leaf-300/60"
        title={t('users.table.caption')}
        contentClassName="p-0 sm:p-0"
      >
        {filterable && (
          <FilterBar label={t('users.table.caption')}>
            <FilterSearch label={t('users.table.column.name')} value={search} onChange={setSearch} />
            <Select
              icon="filter"
              value={role}
              onChange={(event) => setRole(event.target.value)}
              aria-label={t('users.table.column.role')}
              options={[
                { value: 'ALL', label: t('engagements.filter.allStatuses') },
                { value: Role.Owner, label: ROLE_LABELS[Role.Owner] },
                { value: Role.Admin, label: ROLE_LABELS[Role.Admin] },
                { value: Role.Approver, label: ROLE_LABELS[Role.Approver] },
                { value: Role.Editor, label: ROLE_LABELS[Role.Editor] },
                { value: Role.Viewer, label: ROLE_LABELS[Role.Viewer] },
              ]}
            />
          </FilterBar>
        )}

        {directory ? (
          <DataTable
            caption={t('users.table.caption')}
            columns={columns}
            rows={rows}
            rowKey={(member) => member.id}
            emptyMessage={t('users.empty.title')}
          />
        ) : (
          <div className="p-4 sm:p-5">
            <StateBlock
              status={state.status === 'ready' ? 'error' : state.status}
              loadingLabel={t('workspace.state.loading')}
              loadingSkeleton={<DataTableSkeleton columns={3} rows={3} />}
              title={
                state.status === 'empty'
                  ? t('users.empty.title')
                  : state.status === 'forbidden'
                    ? t('workspace.state.forbidden.title')
                    : state.status === 'loading'
                      ? t('workspace.state.loading')
                      : t('users.error.title')
              }
              description={
                state.status === 'empty'
                  ? t('users.empty.description')
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
          </div>
        )}
      </SectionCard>

      <SectionCard className="mt-5 border-dashed">
        <h2 className="text-panel text-forest-900">
          {preview ? t('users.preview.disclosure.title') : t('users.live.disclosure.title')}
        </h2>
        <p className="mt-2 max-w-3xl text-body text-gray-600">
          {preview
            ? t('users.preview.disclosure.description')
            : t('users.live.disclosure.description')}
        </p>
      </SectionCard>
    </div>
  );
}
