import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';
import { ModulePendingNotice } from '@/shell/ModulePendingNotice';
import { RequireTier } from '@/features/rbac/RequireTier';
import { Role } from '@/features/rbac/roles';

const ANCHORS = ['general', 'language', 'residency', 'security', 'integrations', 'about'] as const;

/**
 * Admin+ route (Appendix A); the Security anchor is further gated to
 * Owner via RequireTier — an in-page hide layered on top of the route-level
 * RoleGuard, per §11.7/§19.
 */
export function SettingsPage() {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader title={t('nav.settings')} />
      <div className="flex gap-10">
        <nav aria-label="Settings sections" className="w-50 shrink-0">
          <ul className="flex flex-col gap-1 text-body text-gray-600">
            {ANCHORS.map((anchor) => (
              <li key={anchor}>
                <a
                  href={`#${anchor}`}
                  className="block rounded-s px-3 py-2 capitalize hover:bg-tint-100 hover:text-forest-900"
                >
                  {anchor}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex-1 space-y-6">
          {ANCHORS.filter((anchor) => anchor !== 'security').map((anchor) => (
            <section key={anchor} id={anchor}>
              <h2 className="mb-3 text-panel capitalize text-forest-900">{anchor}</h2>
              <ModulePendingNotice />
            </section>
          ))}
          <RequireTier minTier={Role.Owner}>
            <section id="security">
              <h2 className="mb-3 text-panel capitalize text-forest-900">security</h2>
              <ModulePendingNotice />
            </section>
          </RequireTier>
        </div>
      </div>
    </div>
  );
}
