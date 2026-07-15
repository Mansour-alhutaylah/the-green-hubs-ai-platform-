import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import { ANALYSIS_STATUS_BREAKDOWN, type AnalysisRunStatus } from '@/features/analysis/mockAnalysisData';

/** Same status colors used everywhere else this vocabulary appears
 * (AnalysisStatusBadge, the run-card status rail) — status color is
 * reserved and never doubles as a generic categorical hue. */
const STATUS_COLOR: Record<AnalysisRunStatus, string> = {
  COMPLETE: 'var(--color-leaf-500)',
  PROCESSING: 'var(--color-sky-700)',
  FAILED: 'var(--color-red-700)',
  INSUFFICIENT_EVIDENCE: 'var(--color-amber-700)',
};

const STATUS_LABEL_KEY: Record<AnalysisRunStatus, StringKey> = {
  COMPLETE: 'analysis.status.complete',
  PROCESSING: 'analysis.status.processing',
  FAILED: 'analysis.status.failed',
  INSUFFICIENT_EVIDENCE: 'analysis.status.insufficientEvidence',
};

const SIZE = 168;
const STROKE = 22;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function AnalysisSummaryDonut() {
  const { t } = useLocale();
  const total = ANALYSIS_STATUS_BREAKDOWN.reduce((sum, entry) => sum + entry.count, 0);

  let offset = 0;
  const segments = ANALYSIS_STATUS_BREAKDOWN.filter((entry) => entry.count > 0).map((entry) => {
    const fraction = entry.count / total;
    const dash = fraction * CIRCUMFERENCE;
    const segment = {
      ...entry,
      dash,
      gap: CIRCUMFERENCE - dash,
      dashOffset: -offset,
      percentage: Math.round(fraction * 100),
    };
    offset += dash;
    return segment;
  });

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row sm:items-center sm:justify-center">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        width={SIZE}
        height={SIZE}
        aria-label={t('dashboard.section.analysisSummary')}
        className="shrink-0 -rotate-90"
      >
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke="var(--color-line-200)"
          strokeWidth={STROKE}
        />
        {segments.map((segment) => (
          <circle
            key={segment.status}
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke={STATUS_COLOR[segment.status]}
            strokeWidth={STROKE}
            strokeDasharray={`${segment.dash} ${segment.gap}`}
            strokeDashoffset={segment.dashOffset}
            strokeLinecap={segments.length === 1 ? 'round' : 'butt'}
          />
        ))}
        <text
          x={SIZE / 2}
          y={SIZE / 2 - 4}
          textAnchor="middle"
          className="rotate-90 fill-forest-900 font-bold"
          style={{ fontSize: 26, transformOrigin: `${SIZE / 2}px ${SIZE / 2}px` }}
        >
          {total}
        </text>
        <text
          x={SIZE / 2}
          y={SIZE / 2 + 16}
          textAnchor="middle"
          className="rotate-90 fill-gray-600"
          style={{ fontSize: 10, transformOrigin: `${SIZE / 2}px ${SIZE / 2}px` }}
        >
          {t('dashboard.chart.totalRuns')}
        </text>
      </svg>

      <ul className="w-full space-y-2.5 sm:max-w-48">
        {ANALYSIS_STATUS_BREAKDOWN.map((entry) => (
          <li key={entry.status} className="flex items-center justify-between gap-3 text-meta">
            <span className="flex min-w-0 items-center gap-2">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: STATUS_COLOR[entry.status] }}
                aria-hidden
              />
              <span className="truncate font-semibold text-ink-900">{t(STATUS_LABEL_KEY[entry.status])}</span>
            </span>
            <span className="shrink-0 font-bold text-gray-600">{entry.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
