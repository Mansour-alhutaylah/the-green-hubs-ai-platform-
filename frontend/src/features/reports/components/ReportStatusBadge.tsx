import type { ReportStatus } from '@/lib/data/contracts';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import { cn } from '@/lib/utils/cn';

/**
 * A report's status, as text with a supporting tint.
 *
 * Colour is never the only carrier: every badge prints its own label, so
 * the four statuses remain distinguishable without colour vision and in a
 * greyscale print. `published` deliberately reads as "Published" rather
 * than anything implying filing, assurance, or acceptance by a regulator,
 * because Preview publishes nothing anywhere.
 */
const LABEL_KEY: Record<ReportStatus, StringKey> = {
  draft: 'reports.status.draft',
  inReview: 'reports.status.inReview',
  readyToPublish: 'reports.status.readyToPublish',
  published: 'reports.status.published',
};

const TONE: Record<ReportStatus, string> = {
  draft: 'border-line-300 bg-tint-100 text-gray-600',
  inReview: 'border-amber-200 bg-amber-50 text-amber-700',
  readyToPublish: 'border-leaf-300 bg-leaf-100 text-leaf-700',
  published: 'border-forest-200 bg-forest-50 text-forest-900',
};

export function ReportStatusBadge({ status }: { status: ReportStatus }) {
  const { t } = useLocale();
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-caption font-bold',
        TONE[status],
      )}
    >
      {t(LABEL_KEY[status])}
    </span>
  );
}

/** A compact readiness meter. The number is always printed; the bar is
 * decoration on top of a value that is already readable as text. */
export function ReadinessMeter({ percent }: { percent: number }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-14 shrink-0 overflow-hidden rounded-full bg-tint-100">
        <span
          className="block h-full rounded-full bg-forest-700"
          style={{ width: `${percent}%` }}
          aria-hidden
        />
      </span>
      <span className="text-meta font-bold text-forest-900" dir="ltr">
        {percent}%
      </span>
    </span>
  );
}
