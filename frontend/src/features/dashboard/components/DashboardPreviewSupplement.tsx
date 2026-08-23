import { SectionCard } from '@/design-system';
import { useDashboardPreviewSupplement } from '@/lib/data/hooks/useDashboardData';
import {
  EVIDENCE_REVIEW_STATES,
  type DocumentState,
  type EvidenceReviewState,
} from '@/lib/data/contracts';
import type { StringKey } from '@/lib/i18n/strings/en';
import { useLocale } from '@/lib/i18n/useLocale';

/**
 * The Preview-only dashboard breakdowns.
 *
 * Documents by processing state, the evidence-review lifecycle, an
 * engagement roll-up, and a readiness figure — the four things a complete
 * demonstration workspace shows and that `DashboardSnapshot` does not
 * model.
 *
 * It renders nothing outside Preview. The hook resolves to `unavailable` in
 * a Live build, and the Live dashboard does not mount this component at
 * all, so there are two independent reasons none of these figures can reach
 * a real user's screen.
 *
 * The evidence-review block is a demonstration of the lifecycle's *states*
 * and says so. F2A ships no review action, and who may approve evidence is
 * management decision M-4, still open — showing the states asserts nothing
 * about the authority to move between them.
 */

const DOCUMENT_STATE_LABEL_KEY: Record<DocumentState, StringKey> = {
  pending: 'documents.status.pending',
  processing: 'documents.status.processing',
  processed: 'documents.status.processed',
  failed: 'documents.status.failed',
};

const DOCUMENT_STATES: readonly DocumentState[] = ['processed', 'processing', 'pending', 'failed'];

const EVIDENCE_LABEL_KEY: Record<EvidenceReviewState, StringKey> = {
  pendingReview: 'dashboard.preview.evidence.pendingReview',
  approved: 'dashboard.preview.evidence.approved',
  rejected: 'dashboard.preview.evidence.rejected',
  withdrawn: 'dashboard.preview.evidence.withdrawn',
};

export function DashboardPreviewSupplement() {
  const { t } = useLocale();
  const state = useDashboardPreviewSupplement();

  // Loading, empty, error, forbidden, and unavailable are already stated by
  // the main snapshot view for the same scenario; repeating them here would
  // give a reviewer the same message four times.
  if (state.status !== 'ready') return null;

  const supplement = state.data;

  return (
    <div className="mt-5 grid grid-cols-1 gap-5 xl:mt-6 xl:grid-cols-2 xl:gap-6">
      <SectionCard title={t('dashboard.preview.section.documentStates')}>
        <dl className="grid grid-cols-2 gap-3 min-[30rem]:grid-cols-4">
          {DOCUMENT_STATES.map((documentState) => (
            <div key={documentState} className="rounded-m bg-tint-100 px-3 py-2.5">
              <dt className="text-caption font-semibold text-gray-600">
                {t(DOCUMENT_STATE_LABEL_KEY[documentState])}
              </dt>
              <dd className="mt-0.5 text-title text-forest-900" dir="ltr">
                {supplement.documentsByState[documentState]}
              </dd>
            </div>
          ))}
        </dl>
      </SectionCard>

      <SectionCard
        title={t('dashboard.preview.section.evidenceReview')}
        description={t('dashboard.preview.evidence.note')}
      >
        <dl className="grid grid-cols-2 gap-3 min-[30rem]:grid-cols-4">
          {EVIDENCE_REVIEW_STATES.map((reviewState) => (
            <div key={reviewState} className="rounded-m bg-tint-100 px-3 py-2.5">
              <dt className="text-caption font-semibold text-gray-600">
                {t(EVIDENCE_LABEL_KEY[reviewState])}
              </dt>
              <dd className="mt-0.5 text-title text-forest-900" dir="ltr">
                {supplement.evidenceReview[reviewState]}
              </dd>
            </div>
          ))}
        </dl>
      </SectionCard>

      <SectionCard title={t('dashboard.preview.section.engagements')}>
        <p className="text-caption font-semibold text-gray-600">
          {t('dashboard.preview.engagements.total')}
        </p>
        <p className="text-title text-forest-900" dir="ltr">
          {supplement.engagements.total}
        </p>
        <ul className="mt-3 flex flex-col gap-2">
          {supplement.engagements.byStatus.map((entry) => (
            <li
              key={entry.status}
              className="flex items-center justify-between gap-3 rounded-m bg-tint-100 px-3 py-2"
            >
              <span className="text-meta font-bold text-ink-900" data-user-content>
                {entry.status}
              </span>
              <span className="text-meta text-gray-600" dir="ltr">
                {entry.count}
              </span>
            </li>
          ))}
        </ul>
      </SectionCard>

      <SectionCard
        title={t('dashboard.preview.section.readiness')}
        description={t('dashboard.preview.readiness.detail')}
      >
        <p className="text-caption font-semibold text-gray-600">
          {t('dashboard.preview.readiness.label')}
        </p>
        <p className="text-hero text-forest-900" dir="ltr">
          {t('dashboard.kpi.value.percentage', { value: supplement.readinessPercent })}
        </p>
        {/* The bar is decorative; the figure above it is the accessible
            value, so the meter carries no duplicate announcement. */}
        <span className="mt-3 block h-2 overflow-hidden rounded-full bg-line-200" aria-hidden>
          <span
            className="block h-full rounded-full bg-leaf-500"
            style={{ inlineSize: `${supplement.readinessPercent}%` }}
          />
        </span>
      </SectionCard>
    </div>
  );
}
