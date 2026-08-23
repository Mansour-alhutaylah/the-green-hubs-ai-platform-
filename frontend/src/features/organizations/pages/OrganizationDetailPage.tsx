import { useState, type FormEvent } from 'react';
import { Link, useParams } from 'react-router';
import {
  Button,
  DemoDataBadge,
  Icon,
  Input,
  LoadingSkeleton,
  PartialCoverageNotice,
  SectionCard,
  StateBlock,
} from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { RequireTier } from '@/features/rbac/RequireTier';
import { Role } from '@/features/rbac/roles';
import { useHasMinTier } from '@/features/rbac/useHasMinTier';
import { DetailList } from '@/features/workspace/components/DetailList';
import { useOrganizationDetail, useUpdateOrganization } from '@/lib/data/hooks/useOrganizationData';
import type { OrganizationSummary } from '@/lib/data/contracts';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { PageHeader } from '@/shell/PageHeader';

/**
 * One organization.
 *
 * The id in the route grants nothing. `OrganizationService.get` compares it
 * against the caller's own trusted `organization_id` and raises
 * `NotFoundError` for anything else — deliberately the same answer as a
 * nonexistent id, so a cross-tenant probe is indistinguishable from a typo.
 * This page renders a plain "could not be found" and makes no attempt to
 * tell the two apart.
 *
 * Only the fields `OrganizationResponse` actually exposes are shown. No
 * member count, facility count, sector, or status appears here: no endpoint
 * reports any of them, and a plausible-looking figure with nothing behind
 * it is precisely the failure this page exists to avoid.
 *
 * Renaming requires `organization.manage`, which the backend grants to
 * admin and owner. Below that tier the form is absent and the reason is
 * stated — a control guaranteed to be refused is not an affordance.
 */
export function OrganizationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const preview = isPreviewMode();

  const { state, retry } = useOrganizationDetail(id);
  const organization = state.status === 'ready' ? state.data : null;
  const canManage = useHasMinTier(Role.Admin);

  return (
    <div>
      <PageHeader
        eyebrow={t('organizations.detail.eyebrow')}
        title={organization?.name ?? t('title.organization')}
        action={
          <>
            {preview && <DemoDataBadge label={t('dashboard.sampleData')} />}
            <Link
              to={ROUTES.organizations}
              className="inline-flex min-h-10 items-center gap-2 rounded-m border border-line-200 px-4 text-body font-semibold text-forest-900 transition-colors hover:bg-tint-100"
            >
              <Icon name="chevron-left" size={16} />
              {t('organizations.detail.back')}
            </Link>
          </>
        }
      />

      {state.status === 'ready' && state.coverage === 'partial' && (
        <PartialCoverageNotice message={t('workspace.state.partial')} />
      )}

      {organization ? (
        <div className="flex flex-col gap-5">
          <SectionCard
            title={t('organizations.detail.profile.title')}
            description={t('organizations.detail.profile.description')}
          >
            <DetailList
              items={[
                {
                  id: 'name',
                  label: t('organizations.detail.field.name'),
                  value: <span data-user-content>{organization.name}</span>,
                },
                {
                  id: 'created',
                  label: t('organizations.detail.field.created'),
                  value: organization.createdAt ? (
                    <time dir="ltr">{formatDateTime(organization.createdAt)}</time>
                  ) : (
                    t('workspace.value.notRecorded')
                  ),
                },
              ]}
            />
          </SectionCard>

          <RequireTier minTier={Role.Admin}>
            <RenameForm organization={organization} onRenamed={retry} />
          </RequireTier>

          {!canManage && (
            <SectionCard className="border-dashed">
              <p className="max-w-3xl text-meta text-gray-600">
                {t('organizations.detail.rename.forbidden')}
              </p>
            </SectionCard>
          )}

          <SectionCard className="border-dashed">
            <p className="max-w-3xl text-meta text-gray-600">
              {t('organizations.delete.unavailable')}
            </p>
          </SectionCard>
        </div>
      ) : (
        <SectionCard>
          <StateBlock
            status={state.status === 'ready' ? 'error' : state.status}
            loadingLabel={t('workspace.state.loading')}
            loadingSkeleton={<LoadingSkeleton lines={4} label={t('workspace.state.loading')} />}
            title={
              state.status === 'not-found'
                ? t('workspace.state.notFound.title')
                : state.status === 'forbidden'
                  ? t('workspace.state.forbidden.title')
                  : state.status === 'loading'
                    ? t('workspace.state.loading')
                    : t('organizations.error.title')
            }
            description={
              state.status === 'not-found'
                ? t('workspace.state.notFound.description')
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
    </div>
  );
}

/**
 * `PATCH /api/v1/organizations/{id}` with `{ name }` — the only mutation
 * this contract exposes. The id sent is the one already resolved for this
 * page, which the service has proven is the caller's own.
 *
 * In Preview the form validates and resets without issuing a request.
 */
function RenameForm({
  organization,
  onRenamed,
}: {
  organization: OrganizationSummary;
  onRenamed: () => void;
}) {
  const { t } = useLocale();
  const preview = isPreviewMode();
  const [name, setName] = useState(organization.name);
  const [notice, setNotice] = useState<string | null>(null);

  const update = useUpdateOrganization(t('organizations.detail.rename.error'));

  const trimmed = name.trim();
  const hasChange = trimmed.length > 0 && trimmed !== organization.name;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice(null);
    if (!hasChange) return;

    if (preview) {
      setNotice(t('organizations.detail.rename.preview'));
      setName(organization.name);
      return;
    }

    const updated = await update.run({ organizationId: organization.id, name: trimmed });
    if (updated) {
      setNotice(t('organizations.detail.rename.success'));
      onRenamed();
    }
  }

  return (
    <SectionCard
      title={t('organizations.detail.rename.title')}
      description={t('organizations.detail.rename.description')}
    >
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
        <Input
          label={t('organizations.detail.rename.label')}
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          maxLength={200}
          containerClassName="max-w-lg"
        />

        {update.status === 'failed' && update.error && (
          <p role="alert" className="text-meta text-amber-700">
            {update.error}
          </p>
        )}

        {notice && (
          <output className="block text-meta text-gray-600">{notice}</output>
        )}

        <div>
          <Button
            type="submit"
            disabled={!hasChange}
            isLoading={update.status === 'submitting'}
            loadingLabel={t('organizations.detail.rename.submitting')}
          >
            {t('organizations.detail.rename.submit')}
          </Button>
        </div>
      </form>
    </SectionCard>
  );
}
