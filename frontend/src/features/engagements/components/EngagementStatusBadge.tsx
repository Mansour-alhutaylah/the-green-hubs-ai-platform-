import { StatusBadge, type StatusTone } from '@/design-system';
import type { StringKey } from '@/lib/i18n/strings/en';
import { useLocale } from '@/lib/i18n/useLocale';
import {
  recognizeEngagementStatus,
  type RecognizedEngagementStatus,
} from '@/lib/data/contracts';

/**
 * An engagement's status, rendered without ever discarding what the server
 * actually stored.
 *
 * `engagements.status` is a free-form nullable `varchar(50)` on the
 * backend, not a database enum, and the create schema's own default
 * (`"planning"`) is outside the set this interface has been taught. So the
 * rule is: a *recognized* value gets a translated label and a tone; any
 * other value is rendered **verbatim**, in a neutral tone, rather than
 * being mapped to a nearby-looking status or hidden.
 *
 * Showing an unrecognized status as-is is the honest option. Coercing it to
 * "Draft" would put a word on screen that the record does not contain, and
 * dropping it would tell a reader an engagement has no status when it has
 * one this build simply does not know.
 */
const TONE_BY_STATUS: Record<RecognizedEngagementStatus, StatusTone> = {
  active: 'success',
  draft: 'pending',
  closed: 'neutral',
  archived: 'neutral',
};

const LABEL_KEY_BY_STATUS: Record<RecognizedEngagementStatus, StringKey> = {
  active: 'engagements.status.active',
  draft: 'engagements.status.draft',
  closed: 'engagements.status.closed',
  archived: 'engagements.status.archived',
};

export function EngagementStatusBadge({ status }: { status: string | null }) {
  const { t } = useLocale();
  const recognized = recognizeEngagementStatus(status);

  if (recognized) {
    return <StatusBadge tone={TONE_BY_STATUS[recognized]}>{t(LABEL_KEY_BY_STATUS[recognized])}</StatusBadge>;
  }

  if (status == null || status.trim().length === 0) {
    return <StatusBadge tone="pending">{t('engagements.status.none')}</StatusBadge>;
  }

  // Server-stored text this build has not been taught. Rendered as it is,
  // marked as user/server content so it is never confused with UI copy.
  return (
    <StatusBadge tone="neutral">
      <span data-user-content>{status}</span>
    </StatusBadge>
  );
}
