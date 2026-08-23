import type { ReactNode } from 'react';
import { Icon, Tooltip } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';

/**
 * The four evidence KPIs, and the only place on the dashboard where a
 * headline figure appears.
 *
 * The card that used to sit here was labelled "Compliance Score" over a
 * percentage. No backend computes a regulatory judgement, so the product
 * cannot make one; a number under that label is a legal claim the codebase
 * has no basis for. It is now "Evidence readiness", which describes how
 * much of the workspace's own evidence has reached report-ready, and the
 * tooltip states the definition rather than leaving the reader to guess.
 *
 * `value === null` renders as an explicit unavailable state, never as `0`.
 * A workspace with nothing awaiting review and a workspace whose review
 * count could not be fetched are different situations, and a reader must
 * be able to tell them apart. That rule is enforced here rather than at
 * each call site so a future KPI cannot forget it.
 */

export interface EvidenceKpi {
  readonly id: string;
  readonly label: string;
  /** `null` means "could not be determined", which is not zero. */
  readonly value: number | null;
  readonly unit?: 'percent' | 'count';
  /** Short definition. Prevents a figure being read as a claim it is not. */
  readonly definition: string;
  /** Optional supporting line, e.g. "3 failed extractions". */
  readonly context?: string;
  readonly icon: 'audit' | 'documents' | 'eye' | 'refresh';
  /** Drives the accent on the figure. Meaning, not decoration. */
  readonly tone?: 'neutral' | 'positive' | 'warning';
}

export function EvidenceKpiRow({ items }: { items: readonly EvidenceKpi[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 min-[520px]:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <KpiCard key={item.id} item={item} />
      ))}
    </div>
  );
}

const TONE_CLASS: Record<NonNullable<EvidenceKpi['tone']>, string> = {
  neutral: 'text-forest-900',
  positive: 'text-leaf-700',
  warning: 'text-amber-700',
};

function KpiCard({ item }: { item: EvidenceKpi }) {
  const { t } = useLocale();
  const unavailable = item.value === null;

  return (
    <article className="flex min-w-0 flex-col rounded-l border border-line-200 bg-surface-0 p-4 shadow-card">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-caption font-bold uppercase tracking-wide text-gray-600">
          {item.label}
        </h3>
        <Tooltip content={item.definition}>
          <button
            type="button"
            aria-label={t('dashboard.kpi.definition', { label: item.label })}
            className="shrink-0 rounded-s p-0.5 text-gray-400 transition-colors hover:text-forest-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
          >
            <Icon name={item.icon} size={15} />
          </button>
        </Tooltip>
      </div>

      {unavailable ? (
        <>
          <p className="mt-2 text-panel font-bold text-gray-500">
            {t('workspace.value.unavailable')}
          </p>
          <p className="mt-1 text-caption text-gray-600">
            {t('workspace.value.unavailable.detail')}
          </p>
        </>
      ) : (
        <>
          <p
            className={cn(
              'mt-2 text-hero font-bold leading-none',
              TONE_CLASS[item.tone ?? 'neutral'],
            )}
          >
            <span dir="ltr">{formatValue(item.value, item.unit)}</span>
          </p>
          {item.context && <p className="mt-1.5 text-caption text-gray-600">{item.context}</p>}
        </>
      )}
    </article>
  );
}

function formatValue(value: number, unit: EvidenceKpi['unit']): ReactNode {
  return unit === 'percent' ? `${value}%` : String(value);
}
