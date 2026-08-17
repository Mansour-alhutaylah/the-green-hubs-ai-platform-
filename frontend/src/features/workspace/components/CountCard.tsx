import { Icon, type IconName } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';

/**
 * A single exact count, or an explicit statement that it could not be
 * loaded.
 *
 * This component is where the "`0` and `null` are different claims" rule
 * is actually enforced on screen. `value` is `number | null`, and `null`
 * has no numeric rendering at all — not a dash that reads as zero, not a
 * greyed `0`, not an em dash a reader has to interpret. It renders the
 * word "Unavailable" plus the sentence "This figure could not be loaded.
 * It is not zero."
 *
 * A verified zero, by contrast, renders as `0` like any other measurement,
 * because a workspace with no failed documents genuinely has none.
 *
 * The pair is also distinguishable without color: the unavailable state
 * changes the text itself and carries a warning glyph, so it survives
 * greyscale, low vision, and a screenshot.
 */
export function CountCard({
  label,
  detail,
  value,
  icon,
  className,
}: {
  label: string;
  detail?: string;
  value: number | null;
  icon?: IconName;
  className?: string;
}) {
  const { t } = useLocale();
  const isUnavailable = value == null;

  return (
    <div
      className={cn(
        'surface-lift flex items-start gap-3 rounded-xl border border-line-200 bg-surface-0 p-4 shadow-card',
        className,
      )}
    >
      {icon && (
        <span
          className={cn(
            'flex h-11 w-11 shrink-0 items-center justify-center rounded-l border',
            isUnavailable
              ? 'border-line-200 bg-tint-100 text-gray-600'
              : 'border-leaf-300 bg-leaf-100 text-leaf-700',
          )}
          aria-hidden
        >
          <Icon name={isUnavailable ? 'circle-alert' : icon} size={20} />
        </span>
      )}
      <div className="min-w-0">
        <p className="text-caption font-semibold text-gray-600">{label}</p>
        {isUnavailable ? (
          <>
            <p className="mt-0.5 text-body font-bold text-gray-600">
              {t('workspace.value.unavailable')}
            </p>
            <p className="mt-0.5 text-caption text-gray-600">
              {t('workspace.value.unavailable.detail')}
            </p>
          </>
        ) : (
          <>
            {/* `dir="ltr"` so a figure is never bidi-reordered in Arabic. */}
            <p className="mt-0.5 text-title text-forest-900" dir="ltr">
              {value}
            </p>
            {detail && <p className="mt-0.5 text-caption text-gray-600">{detail}</p>}
          </>
        )}
      </div>
    </div>
  );
}

/**
 * A capability with no service behind it.
 *
 * Compact and specific by design: it names the capability and says nothing
 * provides it yet. It deliberately does not render a zero, a placeholder
 * chart, an empty list, or a "coming soon" marketing panel — each of which
 * would imply either a measurement or a commitment.
 */
export function UnavailableMetricCard({ label, className }: { label: string; className?: string }) {
  const { t } = useLocale();
  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-xl border border-dashed border-line-300 bg-tint-100 p-4',
        className,
      )}
    >
      <span className="mt-0.5 shrink-0 text-gray-600" aria-hidden>
        <Icon name="circle-alert" size={18} />
      </span>
      <div className="min-w-0">
        <p className="text-meta font-bold text-ink-900">{label}</p>
        <p className="mt-0.5 text-caption text-gray-600">
          {t('dashboard.live.unavailable.description')}
        </p>
      </div>
    </div>
  );
}
