import { useState, type FormEvent } from 'react';
import { Button, Input, SectionCard, Select } from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { useWorkspace } from '@/features/organizations/workspace/WorkspaceContext';
import { useCreateEngagement } from '@/lib/data/hooks/useEngagementData';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';
import { DetailList } from '@/features/workspace/components/DetailList';

/**
 * The create-engagement form.
 *
 * The security-relevant part is what this form *does not* contain: there
 * is no organization input, no organization select, and no code path that
 * reads an organization from the URL, a route parameter, a query string, or
 * storage.
 *
 * `organization_id` is required by `EngagementCreateRequest`, and the only
 * value ever sent is `activeOrgId` from the authenticated session — which
 * a Live session sets exactly once, from the `organization_id` in
 * `GET /api/v1/auth/me`, and never changes (`setActiveOrg` is a no-op in
 * the live auth service). The organization is rendered as read-only
 * context so the person knows where the engagement is going, not as a
 * field they could point elsewhere.
 *
 * Even if that value were tampered with, the service compares it against
 * the caller's own trusted organization and answers 403 — the client-side
 * discipline here is defence in depth, not the boundary.
 *
 * In Preview the form validates and resets without issuing a request. The
 * submit handler returns before `run()` is reached, so there is no network
 * call to intercept rather than a call that happens to be stubbed.
 */
export function EngagementCreateForm({
  onCancel,
  onCreated,
  className,
}: {
  onCancel: () => void;
  onCreated: () => void;
  className?: string;
}) {
  const { t } = useLocale();
  const { activeOrgId } = useAuth();
  const workspace = useWorkspace();
  const preview = isPreviewMode();

  const [title, setTitle] = useState('');
  const [status, setStatus] = useState('');
  const [titleError, setTitleError] = useState<string | null>(null);
  const [previewNotice, setPreviewNotice] = useState<string | null>(null);

  const create = useCreateEngagement(t('engagements.create.error'));

  const canSubmit = activeOrgId != null && title.trim().length > 0;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPreviewNotice(null);

    if (title.trim().length === 0) {
      setTitleError(t('engagements.create.field.title'));
      return;
    }
    setTitleError(null);

    if (preview) {
      // Preview never reaches the network. Nothing below this line runs.
      setPreviewNotice(t('engagements.create.preview'));
      setTitle('');
      setStatus('');
      return;
    }

    if (activeOrgId == null) return;

    const created = await create.run({
      // The server's own answer about which organization this account
      // belongs to. Never a URL, a route param, or an editable field.
      organizationId: activeOrgId,
      title: title.trim(),
      // Omitted entirely when unset, so the service applies its default.
      // Never sent as null: the schema types `status` as a plain string.
      ...(status ? { status } : {}),
    });

    if (created) {
      setTitle('');
      setStatus('');
      onCreated();
    }
  }

  return (
    <SectionCard
      className={className}
      title={t('engagements.create.title')}
      description={t('engagements.create.description')}
    >
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        <DetailList
          items={[
            {
              id: 'organization',
              label: t('engagements.create.organization.label'),
              value: (
                <>
                  <span data-user-content>
                    {workspace.organization?.name ?? t('workspace.value.notRecorded')}
                  </span>
                  <span className="mt-1 block text-caption text-gray-600">
                    {t('engagements.create.organization.hint')}
                  </span>
                </>
              ),
            },
          ]}
        />

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label={t('engagements.create.field.title')}
            placeholder={t('engagements.create.field.title.placeholder')}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            error={titleError ?? undefined}
            required
            maxLength={255}
          />
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="engagement-create-status"
              className="text-meta font-bold text-ink-900"
            >
              {t('engagements.create.field.status')}
            </label>
            <Select
              id="engagement-create-status"
              controlSize="md"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              aria-describedby="engagement-create-status-hint"
              options={[
                { value: '', label: t('engagements.create.field.status.default') },
                { value: 'active', label: t('engagements.status.active') },
                { value: 'draft', label: t('engagements.status.draft') },
                { value: 'closed', label: t('engagements.status.closed') },
                { value: 'archived', label: t('engagements.status.archived') },
              ]}
            />
            <p id="engagement-create-status-hint" className="text-caption text-gray-600">
              {t('engagements.create.field.status.hint')}
            </p>
          </div>
        </div>

        {activeOrgId == null && (
          <p role="alert" className="text-meta text-amber-700">
            {t('engagements.create.organization.missing')}
          </p>
        )}

        {create.status === 'failed' && create.error && (
          <p role="alert" className="text-meta text-amber-700">
            {create.error}
          </p>
        )}

        {previewNotice && (
          <output className="block text-meta text-gray-600">{previewNotice}</output>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="submit"
            disabled={!canSubmit}
            isLoading={create.status === 'submitting'}
            loadingLabel={t('engagements.create.submitting')}
          >
            {t('engagements.create.submit')}
          </Button>
          <Button type="button" variant="ghost" onClick={onCancel}>
            {t('engagements.create.cancel')}
          </Button>
        </div>
      </form>
    </SectionCard>
  );
}
