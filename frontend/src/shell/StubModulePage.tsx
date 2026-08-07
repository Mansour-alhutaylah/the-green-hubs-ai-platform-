import { Badge, DiamondGlyph } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from './PageHeader';
import { ModulePendingNotice } from './ModulePendingNotice';

export interface StubModulePageProps {
  title: string;
  subtitle?: string;
}

/**
 * Phase 1 placeholder for an MVP route whose business logic (real tables,
 * charts, forms) ships in a later phase. Exists so routing, layout,
 * breadcrumbs, and RBAC gating are provable end to end right now — see
 * Appendix A for which tier reaches which route.
 *
 * Carries the same "Coming soon" eyebrow and "Soon" badge as
 * `ComingSoonPage`, so every not-yet-available module reads as one
 * consistent state regardless of which of the two placeholder components
 * happens to back it.
 */
export function StubModulePage({ title, subtitle }: StubModulePageProps) {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader
        eyebrow={t('placeholder.eyebrow')}
        title={title}
        subtitle={subtitle}
        action={
          <Badge className="border-leaf-300 bg-leaf-100 text-leaf-700">
            <DiamondGlyph variant="hollow" size={8} />
            {t('nav.soon')}
          </Badge>
        }
      />
      <ModulePendingNotice />
    </div>
  );
}
