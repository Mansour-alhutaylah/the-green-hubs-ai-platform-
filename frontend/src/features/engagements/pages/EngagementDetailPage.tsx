import { Link, useParams } from 'react-router';
import {
  Button,
  DemoDataBadge,
  Icon,
  LoadingSkeleton,
  PartialCoverageNotice,
  SectionCard,
  StateBlock,
} from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { RequireTier } from '@/features/rbac/RequireTier';
import { Role } from '@/features/rbac/roles';
import { useWorkspace } from '@/features/organizations/workspace/WorkspaceContext';
import { DetailList } from '@/features/workspace/components/DetailList';
import { useEngagementDetail } from '@/lib/data/hooks/useEngagementData';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { PageHeader } from '@/shell/PageHeader';
import { EngagementStatusBadge } from '../components/EngagementStatusBadge';
import { EngagementEditForm } from '../components/EngagementEditForm';

/**
 * One engagement.
 *
 * The id comes from the route, which is safe here for the reason the
 * backend made it safe: `EngagementService.get` looks the row up with a
 * tenant-scoped query and answers `NotFoundError` for anything outside the
 * caller's own organization — the *same* answer as a genuinely
 * nonexistent id. So a route parameter grants nothing and reveals nothing,
 * and this page renders 404 without trying to distinguish the two cases.
 *
 * The organization shown is the caller's own workspace name, not a lookup
 * driven by the engagement's `organization_id`. That field is display
 * context on a record the server already scoped; using it to fetch
 * anything would be treating a response value as an authority.
 *
 * The related-documents card links to the Documents page filtered by this
 * engagement rather than stating a count. The documents endpoint does
 * report an exact `total` for an engagement filter, but this page has not
 * requested it, and a number nobody measured is exactly what F2A exists to
 * avoid — so it offers the route to the real figure instead of inventing
 * one.
 */
export function EngagementDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const workspace = useWorkspace();
  const preview = isPreviewMode();

  const { state, retry } = useEngagementDetail(id);
  const engagement = state.status === 'ready' ? state.data : null;

  return (
    <div>
      <PageHeader
        eyebrow={t('engagements.detail.eyebrow')}
        title={engagement?.title ?? t('title.engagement')}
        subtitle={engagement ? undefined : t('engagements.subtitle')}
        action={
          <>
            {preview && <DemoDataBadge label={t('dashboard.sampleData')} />}
            <Link
              to={ROUTES.engagements}
              className="inline-flex min-h-10 items-center gap-2 rounded-m border border-line-200 px-4 text-body font-semibold text-forest-900 transition-colors hover:bg-tint-100"
            >
              <Icon name="chevron-left" size={16} />
              {t('engagements.detail.back')}
            </Link>
          </>
        }
      />

      {state.status === 'ready' && state.coverage === 'partial' && (
        <PartialCoverageNotice message={t('workspace.state.partial')} />
      )}

      {engagement ? (
        <div className="flex flex-col gap-5">
          <SectionCard
            title={t('engagements.detail.profile.title')}
            description={t('engagements.detail.profile.description')}
          >
            <DetailList
              items={[
                {
                  id: 'title',
                  label: t('engagements.detail.field.title'),
                  value: <span data-user-content>{engagement.title}</span>,
                },
                {
                  id: 'status',
                  label: t('engagements.detail.field.status'),
                  value: <EngagementStatusBadge status={engagement.status} />,
                },
                {
                  id: 'organization',
                  label: t('engagements.detail.field.organization'),
                  value: (
                    <span data-user-content>
                      {workspace.organization?.name ?? t('workspace.value.notRecorded')}
                    </span>
                  ),
                },
                {
                  id: 'created',
                  label: t('engagements.detail.field.created'),
                  value: engagement.createdAt ? (
                    <time dir="ltr">{formatDateTime(engagement.createdAt)}</time>
                  ) : (
                    t('workspace.value.notRecorded')
                  ),
                },
              ]}
            />
          </SectionCard>

          {/* `engagement.manage` is editor-and-above on this backend, so the
              form is absent below that tier rather than shown and refused. */}
          <RequireTier minTier={Role.Editor}>
            <EngagementEditForm engagement={engagement} onUpdated={retry} />
          </RequireTier>

          <SectionCard
            title={t('engagements.detail.documents.title')}
            description={t('engagements.detail.documents.description')}
          >
            {/*
              The filter is applied only in Live, where documents really are
              keyed by engagement id. The Preview document fixtures predate
              the engagement fixtures and are grouped by name, so passing an
              id there would filter the list down to nothing and call that
              "this engagement's documents".
            */}
            <Link
              to={
                preview
                  ? ROUTES.documents
                  : `${ROUTES.documents}?engagement=${encodeURIComponent(engagement.id)}`
              }
              className="inline-flex min-h-10 items-center gap-2 rounded-m bg-forest-900 px-4 text-body font-semibold text-white transition-colors hover:bg-forest-800"
            >
              <Icon name="documents" size={16} />
              {t('engagements.detail.documents.action')}
            </Link>
            <p className="mt-3 text-caption text-gray-600">
              {t('engagements.detail.delete.unavailable')}
            </p>
          </SectionCard>
        </div>
      ) : (
        <SectionCard>
          <StateBlock
            status={state.status === 'ready' ? 'error' : state.status}
            loadingLabel={t('workspace.state.loading')}
            loadingSkeleton={<LoadingSkeleton lines={5} label={t('workspace.state.loading')} />}
            title={
              state.status === 'not-found'
                ? t('workspace.state.notFound.title')
                : state.status === 'forbidden'
                  ? t('workspace.state.forbidden.title')
                  : state.status === 'loading'
                    ? t('workspace.state.loading')
                    : t('workspace.state.error.title')
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
