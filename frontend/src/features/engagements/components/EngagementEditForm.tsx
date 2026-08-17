import { useState, type FormEvent } from 'react';
import { Button, Input, SectionCard, Select } from '@/design-system';
import { useUpdateEngagement } from '@/lib/data/hooks/useEngagementData';
import type { EngagementSummary } from '@/lib/data/contracts';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';

/**
 * The edit-engagement form.
 *
 * Two fields, because two fields are what the contract allows to change:
 * `title` and `status`. `organization_id` is modelled nowhere in the
 * update path — the service refuses a reassignment anyway, and offering a
 * control for it would advertise a capability that does not exist.
 *
 * Only *changed* fields are sent. The backend rejects an empty `{}` body
 * and rejects an explicitly-null field, so "omitted means unchanged" is
 * the only shape this contract accepts, and the diff below is what
 * produces it.
 *
 * Preview validates and resets without a request, the same as create.
 */
export function EngagementEditForm({
  engagement,
  onUpdated,
  className,
}: {
  engagement: EngagementSummary;
  onUpdated: () => void;
  className?: string;
}) {
  const { t } = useLocale();
  const preview = isPreviewMode();

  const [title, setTitle] = useState(engagement.title);
  const [status, setStatus] = useState(engagement.status ?? '');
  const [notice, setNotice] = useState<string | null>(null);

  const update = useUpdateEngagement(t('engagements.detail.edit.error'));

  const trimmedTitle = title.trim();
  const nextStatus = status.trim();
  const titleChanged = trimmedTitle.length > 0 && trimmedTitle !== engagement.title;
  const statusChanged = nextStatus.length > 0 && nextStatus !== (engagement.status ?? '');
  const hasChanges = titleChanged || statusChanged;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice(null);
    if (!hasChanges) return;

    if (preview) {
      setNotice(t('engagements.create.preview'));
      setTitle(engagement.title);
      setStatus(engagement.status ?? '');
      return;
    }

    const updated = await update.run({
      engagementId: engagement.id,
      // Only what actually changed. An unchanged field is omitted, never
      // resent and never nulled.
      ...(titleChanged ? { title: trimmedTitle } : {}),
      ...(statusChanged ? { status: nextStatus } : {}),
    });

    if (updated) {
      setNotice(t('engagements.detail.edit.success'));
      onUpdated();
    }
  }

  return (
    <SectionCard
      className={className}
      title={t('engagements.detail.edit.title')}
      description={t('engagements.detail.edit.description')}
    >
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Input
            label={t('engagements.detail.field.title')}
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            required
            maxLength={255}
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="engagement-edit-status" className="text-meta font-bold text-ink-900">
              {t('engagements.detail.field.status')}
            </label>
            <Select
              id="engagement-edit-status"
              controlSize="md"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
              options={[
                // The engagement's own stored value stays selectable even
                // when this build does not recognize it, so saving the
                // title never silently rewrites a status it did not know.
                ...(engagement.status && !isRecognized(engagement.status)
                  ? [{ value: engagement.status, label: engagement.status }]
                  : []),
                { value: '', label: t('engagements.status.none') },
                { value: 'active', label: t('engagements.status.active') },
                { value: 'draft', label: t('engagements.status.draft') },
                { value: 'closed', label: t('engagements.status.closed') },
                { value: 'archived', label: t('engagements.status.archived') },
              ]}
            />
          </div>
        </div>

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
            disabled={!hasChanges}
            isLoading={update.status === 'submitting'}
            loadingLabel={t('engagements.detail.edit.submitting')}
          >
            {t('engagements.detail.edit.submit')}
          </Button>
        </div>
      </form>
    </SectionCard>
  );
}

const RECOGNIZED = new Set(['active', 'draft', 'closed', 'archived']);

function isRecognized(status: string): boolean {
  return RECOGNIZED.has(status.trim().toLowerCase());
}
