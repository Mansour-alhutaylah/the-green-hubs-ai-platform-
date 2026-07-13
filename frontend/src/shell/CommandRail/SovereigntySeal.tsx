import { Icon, Tooltip } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';

/** §3.1/§12: "quiet confidence" — present on every screen, prominent on
 * none. Non-interactive except for a hover tooltip explaining data
 * residency; never a marketing banner. */
export function SovereigntySeal({ collapsed }: { collapsed: boolean }) {
  const { t, dir } = useLocale();
  const content = (
    <div className="relative z-10 mx-3 mb-3 mt-auto flex items-center gap-3 rounded-m border border-rail-hairline bg-white/5 px-3 py-3">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-m bg-leaf-500/15 text-leaf-300">
        <Icon name="shield-check" size={15} />
      </span>
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
    <Tooltip
      content={`${t('sovereignty.line1')} · ${t('sovereignty.line2')}`}
      side={dir === 'rtl' ? 'left' : 'right'}
    >
      {content}
    </Tooltip>
  );
}
