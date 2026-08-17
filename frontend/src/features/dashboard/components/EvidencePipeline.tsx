import type { EvidencePipelineStage, EvidenceStage } from '@/lib/data/contracts';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';

/**
 * The evidence lifecycle, uploaded through report-ready.
 *
 * Each stage shows its own count and, from the second stage on, how many
 * documents did not carry through from the previous one. The drop-off is
 * the useful number: "79 verified" is a fact, but "12 analyzed documents
 * have not been verified" is the one that tells someone where the work is.
 *
 * Bars are sized against the first stage, so the visual is a funnel rather
 * than five bars each scaled to itself. Every bar also prints its count as
 * text, because a bar whose only value is its width is unreadable to a
 * screen reader and imprecise to everyone else.
 *
 * Preview only. No endpoint reports a verified or report-ready count, so
 * the Live dashboard names those capabilities as unavailable instead of
 * rendering this with zeros.
 */

const STAGE_LABEL_KEY: Record<EvidenceStage, StringKey> = {
  uploaded: 'dashboard.pipeline.uploaded',
  extracted: 'dashboard.pipeline.extracted',
  analyzed: 'dashboard.pipeline.analyzed',
  verified: 'dashboard.pipeline.verified',
  reportReady: 'dashboard.pipeline.reportReady',
};

export function EvidencePipeline({ stages }: { stages: readonly EvidencePipelineStage[] }) {
  const { t } = useLocale();

  const first = stages[0]?.count ?? 0;
  const scale = Math.max(1, first);

  return (
    <ol className="flex flex-col gap-2.5">
      {stages.map((stage, index) => {
        const previous = index === 0 ? null : stages[index - 1]!.count;
        const dropOff = previous === null ? null : previous - stage.count;
        const widthPercent = Math.max(2, Math.round((stage.count / scale) * 100));

        return (
          <li key={stage.stage} className="min-w-0">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
              <span className="text-meta font-semibold text-forest-900">
                {t(STAGE_LABEL_KEY[stage.stage])}
              </span>
              <span className="flex items-baseline gap-2">
                <span className="text-meta font-bold text-forest-900" dir="ltr">
                  {stage.count}
                </span>
                {dropOff !== null && dropOff > 0 && (
                  <span className="text-caption text-amber-700">
                    {t('dashboard.pipeline.dropOff', { count: dropOff })}
                  </span>
                )}
              </span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-tint-100">
              <div
                className="h-full rounded-full bg-leaf-500"
                style={{ width: `${widthPercent}%` }}
                aria-hidden
              />
            </div>
          </li>
        );
      })}
    </ol>
  );
}
