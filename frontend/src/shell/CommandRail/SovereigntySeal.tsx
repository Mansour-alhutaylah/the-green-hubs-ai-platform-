import { Icon, Tooltip } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';

/** §3.1/§12: "quiet confidence" — present on every screen, prominent on
 * none. Non-interactive except for a hover tooltip explaining data
 * residency; never a marketing banner. */
export function SovereigntySeal({ collapsed }: { collapsed: boolean }) {
  const { t } = useLocale();
  const content = (
    <div className="mt-auto flex items-center gap-3 border-t border-rail-hairline px-6 py-6">
      <Icon name="shield-check" size={14} className="shrink-0 text-rail-muted" />
      {!collapsed && (
        <div className="text-micro leading-tight text-rail-muted">
          <p>{t('sovereignty.line1')}</p>
          <p>{t('sovereignty.line2')}</p>
        </div>
      )}
    </div>
  );

  if (!collapsed) return content;

  return (
    <Tooltip content={`${t('sovereignty.line1')} · ${t('sovereignty.line2')}`} side="right">
      {content}
    </Tooltip>
  );
}
