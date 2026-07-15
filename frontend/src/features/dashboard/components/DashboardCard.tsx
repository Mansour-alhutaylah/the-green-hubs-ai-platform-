import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { Icon, type IconName } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';

export interface DashboardCardProps {
  title: string;
  viewAllHref?: string;
  eyebrow?: string;
  icon?: IconName;
  tone?: 'default' | 'mint' | 'priority';
  children: ReactNode;
}

/** The one card chrome every dashboard section shares (title + optional
 * "View all" link into the corresponding module) — kept in one place so
 * the five sections read as one consistent surface, not five hand-rolled
 * boxes. */
export function DashboardCard({
  title,
  viewAllHref,
  eyebrow,
  icon,
  tone = 'default',
  children,
}: DashboardCardProps) {
  const { t } = useLocale();
  return (
    <section
      className={cn(
        'overflow-hidden rounded-xl border p-4 shadow-card sm:p-5',
        tone === 'default' && 'border-line-200 bg-surface-0',
        tone === 'mint' && 'border-leaf-300/70 bg-mist-50',
        tone === 'priority' && 'border-leaf-300 bg-surface-0 shadow-raise',
      )}
    >
      <div className="mb-4 flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          {icon && (
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-m bg-leaf-100 text-leaf-700">
              <Icon name={icon} size={18} />
            </span>
          )}
          <div className="min-w-0">
            {eyebrow && <p className="type-label mb-0.5 text-leaf-700">{eyebrow}</p>}
            <h2 className="text-panel text-forest-900">{title}</h2>
          </div>
        </div>
        {viewAllHref && (
          <Link
            to={viewAllHref}
            className="inline-flex min-h-8 shrink-0 items-center rounded-m px-2 text-meta font-bold text-leaf-700 transition-colors hover:bg-leaf-100"
          >
            {t('dashboard.viewAll')}
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}
