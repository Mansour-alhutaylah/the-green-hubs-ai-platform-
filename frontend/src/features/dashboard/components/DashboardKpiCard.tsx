import { Icon } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';
import type { MockKpi } from '../mockDashboardData';

const TONE_CLASSES: Record<MockKpi['tone'], string> = {
  positive: 'text-leaf-700',
  neutral: 'text-gray-600',
  attention: 'text-amber-700',
};

const VISUAL_CLASSES: Record<
  MockKpi['visual'],
  { icon: string; rail: string; signal: string }
> = {
  documents: {
    icon: 'bg-mint-100 text-forest-800',
    rail: 'bg-leaf-500',
    signal: 'bg-leaf-300',
  },
  reports: {
    icon: 'bg-sky-100 text-sky-700',
    rail: 'bg-sky-700',
    signal: 'bg-sky-100',
  },
  compliance: {
    icon: 'bg-forest-900 text-white',
    rail: 'bg-forest-700',
    signal: 'bg-leaf-500',
  },
  approval: {
    icon: 'bg-amber-100 text-amber-700',
    rail: 'bg-amber-700',
    signal: 'bg-amber-100',
  },
};

export function DashboardKpiCard({ kpi }: { kpi: MockKpi }) {
  const { t } = useLocale();
  const visual = VISUAL_CLASSES[kpi.visual];

  return (
    <article className="surface-lift relative overflow-hidden rounded-xl border border-line-200 bg-surface-0 p-4 shadow-card sm:p-5">
      <span className={cn('absolute inset-y-0 start-0 w-1', visual.rail)} aria-hidden />
      <div className="flex items-start justify-between gap-3">
        <p className="type-label pt-1 text-gray-600">{t(kpi.labelKey)}</p>
        <span
          className={cn(
            'flex h-10 w-10 shrink-0 items-center justify-center rounded-l',
            visual.icon,
          )}
        >
          <Icon name={kpi.icon} size={20} />
        </span>
      </div>

      <div className="mt-3 flex items-end justify-between gap-4">
        <div>
          <p className="text-metric text-forest-900 sm:text-hero">{kpi.value}</p>
          <p className={cn('mt-1 text-meta font-semibold', TONE_CLASSES[kpi.tone])}>
            {t(kpi.captionKey)}
          </p>
        </div>
        {kpi.progress == null && (
          <span className="flex h-9 items-end gap-1 opacity-70" aria-hidden>
            {[35, 58, 44, 78].map((height) => (
              <span
                key={height}
                className={cn('w-1.5 rounded-full', visual.signal)}
                style={{ height: `${height}%` }}
              />
            ))}
          </span>
        )}
      </div>

      {kpi.progress != null && (
        <div className="mt-4">
          <progress
            className="sr-only"
            aria-label={t(kpi.labelKey)}
            max={100}
            value={kpi.progress}
          >
            {kpi.progress}%
          </progress>
          <div className="h-1.5 overflow-hidden rounded-full bg-line-200" aria-hidden>
            <div
              className="h-full rounded-full bg-leaf-500"
              style={{ width: `${kpi.progress}%` }}
            />
          </div>
        </div>
      )}
    </article>
  );
}
