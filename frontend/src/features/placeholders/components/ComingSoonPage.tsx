import { Link } from 'react-router';
import { Badge, DiamondGlyph, Icon, type IconName } from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';

export interface ComingSoonPageProps {
  title: string;
  icon: IconName;
  description: string;
  unlock: string;
}

/** Shared routed state for navigation items whose business module is not
 * implemented yet. It keeps the shell informative instead of leaving an
 * unexplained content canvas. */
export function ComingSoonPage({ title, icon, description, unlock }: ComingSoonPageProps) {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader
        eyebrow={t('placeholder.eyebrow')}
        title={title}
        subtitle={description}
        action={
          <Badge className="border-leaf-300 bg-leaf-100 text-leaf-700">
            <DiamondGlyph variant="hollow" size={8} />
            {t('nav.soon')}
          </Badge>
        }
      />

      <section className="relative overflow-hidden rounded-xl border border-leaf-300/70 bg-surface-0 p-5 shadow-card sm:p-7 lg:p-9">
        <span
          className="absolute -end-20 -top-24 h-64 w-64 rounded-full border border-leaf-300/40 bg-mist-50"
          aria-hidden
        />
        <div className="relative z-10 grid gap-6 lg:grid-cols-[auto_minmax(0,1fr)] lg:items-center">
          <span className="flex h-16 w-16 items-center justify-center rounded-xl bg-forest-900 text-leaf-300 shadow-brand">
            <Icon name={icon} size={28} />
          </span>
          <div className="max-w-3xl">
            <Badge className="border-leaf-300 bg-mist-50 text-leaf-700">
              {t('nav.soon')}
            </Badge>
            <h2 className="mt-3 text-title text-forest-900">{description}</h2>
            <p className="mt-2 text-body leading-7 text-gray-600">{unlock}</p>
            <Link
              to={ROUTES.dashboard}
              className="mt-5 inline-flex min-h-11 items-center justify-center gap-2 rounded-m bg-forest-900 px-5 text-meta font-bold text-white shadow-card transition-colors hover:bg-forest-950"
            >
              <Icon name="dashboard" size={17} />
              {t('errors.backToDashboard')}
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
