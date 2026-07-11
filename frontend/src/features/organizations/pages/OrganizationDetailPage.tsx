import { useParams, useSearchParams } from 'react-router';
import { cn } from '@/lib/utils/cn';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';
import { ModulePendingNotice } from '@/shell/ModulePendingNotice';

const TABS = ['profile', 'facilities', 'members'] as const;
type Tab = (typeof TABS)[number];

/**
 * Org detail's profile|facilities|members split (§6.6) is implemented as
 * plain buttons + a `?tab=` query param rather than a generic Tabs
 * primitive — a reusable Tabs component would be premature with only this
 * one (stub) consumer; §19 still wants filter/tab state to survive reload,
 * which the query param gives for free.
 */
export function OrganizationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab: Tab = TABS.includes(searchParams.get('tab') as Tab)
    ? (searchParams.get('tab') as Tab)
    : 'profile';

  return (
    <div>
      <PageHeader title={t('nav.organizations')} subtitle={id} />
      <div className="mb-6 flex gap-1 border-b border-line-200">
        {TABS.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setSearchParams({ tab })}
            className={cn(
              'border-b-2 px-4 py-2 text-body capitalize text-gray-600',
              activeTab === tab && 'border-forest-900 font-semibold text-forest-900',
              activeTab !== tab && 'border-transparent',
            )}
          >
            {tab}
          </button>
        ))}
      </div>
      <ModulePendingNotice />
    </div>
  );
}
