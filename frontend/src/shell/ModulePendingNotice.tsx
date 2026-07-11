import { DiamondGlyph } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';

export interface ModulePendingNoticeProps {
  className?: string;
}

/**
 * The shared "this is a real, routed, RBAC-gated screen — its business
 * logic just isn't built yet" notice, used by every MVP-scope stub (§7's
 * Reports/Documents/Analysis/Organizations/Users/Settings/Notifications)
 * and by Organization Detail's tabs / Settings' anchors, which have their
 * own page chrome around this same inner notice. One quiet visual so all
 * of these read as the same considered state rather than N separately
 * hand-rolled placeholder boxes.
 */
export function ModulePendingNotice({ className }: ModulePendingNoticeProps) {
  const { t } = useLocale();
  return (
    <div
      className={cn(
        'flex flex-col items-center gap-3 rounded-l border border-line-200 bg-surface-0 px-8 py-12 text-center',
        className,
      )}
    >
      <DiamondGlyph variant="hollow" size={26} className="text-gray-400" />
      <p className="max-w-95 text-body text-gray-600">{t('stub.laterPhase')}</p>
    </div>
  );
}
