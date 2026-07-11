import { Button, Icon, useToast, type IconName } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';

export interface PlaceholderModulePageProps {
  title: string;
  /** The module's own Command Rail icon — ties the placeholder visually
   * back to the nav item that links here, instead of a generic glyph. */
  icon: IconName;
  /** One sentence: what the module will do. */
  description: string;
  /** One sentence: what unlocks it. */
  unlock: string;
}

/**
 * §11.8 future-module placeholder pattern: real chrome (a PageHeader, same
 * as any shipped module) with the content zone as a quiet, bordered notice
 * — never a marketing splash, never a tiled/checkerboard texture, never a
 * stock illustration. The one available action ("Notify me when available")
 * writes a notification preference; Phase 1 stands that up as a toast
 * confirmation since the Notifications module itself is a later phase's
 * business logic.
 */
export function PlaceholderModulePage({
  title,
  icon,
  description,
  unlock,
}: PlaceholderModulePageProps) {
  const { t } = useLocale();
  const { showToast } = useToast();

  return (
    <div>
      <PageHeader title={title} />
      <div className="rounded-l border border-line-200 bg-surface-0 px-8 py-14">
        <div className="mx-auto flex max-w-105 flex-col items-center text-center">
          <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-tint-100 text-gray-500">
            <Icon name={icon} size={24} />
          </div>
          <p className="type-label mt-5 text-leaf-700">{t('placeholder.eyebrow')}</p>
          <h2 className="mt-2 text-panel text-forest-900">{description}</h2>
          <p className="mt-2 text-body text-gray-600">{unlock}</p>
          <Button
            variant="ghost"
            className="mt-6"
            onClick={() => showToast(t('placeholder.notify'), { kind: 'success' })}
          >
            {t('placeholder.notify')}
          </Button>
        </div>
      </div>
    </div>
  );
}
