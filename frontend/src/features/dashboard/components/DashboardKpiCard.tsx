import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';
import type { MockKpi } from '../mockDashboardData';

const TONE_CLASSES: Record<MockKpi['tone'], string> = {
  positive: 'text-leaf-700',
  neutral: 'text-gray-600',
  attention: 'text-amber-700',
};

export function DashboardKpiCard({ kpi }: { kpi: MockKpi }) {
  const { t } = useLocale();
  return (
    <div className="rounded-l border border-line-200 bg-surface-0 p-5">
      <p className="type-label text-gray-600">{t(kpi.labelKey)}</p>
      <p className="mt-2 text-metric text-forest-900">{kpi.value}</p>
      <p className={cn('mt-1 text-meta font-medium', TONE_CLASSES[kpi.tone])}>
        {t(kpi.captionKey)}
      </p>
    </div>
  );
}
