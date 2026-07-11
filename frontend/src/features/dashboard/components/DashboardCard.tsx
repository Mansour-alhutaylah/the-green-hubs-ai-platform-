import type { ReactNode } from 'react';
import { Link } from 'react-router';
import { useLocale } from '@/lib/i18n/useLocale';

export interface DashboardCardProps {
  title: string;
  viewAllHref?: string;
  children: ReactNode;
}

/** The one card chrome every dashboard section shares (title + optional
 * "View all" link into the corresponding module) — kept in one place so
 * the five sections read as one consistent surface, not five hand-rolled
 * boxes. */
export function DashboardCard({ title, viewAllHref, children }: DashboardCardProps) {
  const { t } = useLocale();
  return (
    <section className="rounded-l border border-line-200 bg-surface-0 p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-panel text-forest-900">{title}</h2>
        {viewAllHref && (
          <Link
            to={viewAllHref}
            className="shrink-0 text-meta font-medium text-leaf-700 hover:underline"
          >
            {t('dashboard.viewAll')}
          </Link>
        )}
      </div>
      {children}
    </section>
  );
}
