import { DiamondGlyph } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';

export interface PreviewNoticeProps {
  className?: string;
}

/**
 * Controlled internal MVP preview disclosure. States, in one quiet line,
 * that parts of the surrounding screen are sample content and which
 * capability is actually live today — so a reviewer never has to infer
 * which figures are real. Deliberately styled as a neutral informational
 * strip (mist/leaf, the same family as ModulePendingNotice) rather than an
 * alert tone: it reports scope, it does not report a fault.
 */
export function PreviewNotice({ className }: PreviewNoticeProps) {
  const { t } = useLocale();

  return (
    <aside
      aria-label={t('preview.label')}
      className={cn(
        'mb-4 flex items-start gap-3 rounded-l border border-leaf-300/70 bg-mist-50 px-4 py-3 sm:mb-5',
        className,
      )}
    >
      <DiamondGlyph variant="hollow" size={12} className="mt-1 shrink-0 text-leaf-700" />
      <p className="text-meta leading-6 text-gray-600">
        <span className="font-bold text-forest-900">{t('preview.label')}</span>
        {' — '}
        {t('preview.notice')}
      </p>
    </aside>
  );
}
