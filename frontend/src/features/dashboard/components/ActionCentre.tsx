import { Link } from 'react-router';
import { Icon } from '@/design-system';
import { PROTECTED_ROUTE_PATHS } from '@/app/router/routeRegistry';
import type { ActionSeverity, EvidenceAction } from '@/lib/data/contracts';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import { cn } from '@/lib/utils/cn';

/**
 * The prioritized Action Centre: what to do next, ordered by how much it
 * matters.
 *
 * Every row is a `Link` to a registered route. There is no `onClick` that
 * shows a toast, no disabled button with a "coming soon" title, and no
 * anchor to `#`. That is enforced rather than intended: `isRegisteredRoute`
 * checks each action's path against `PROTECTED_ROUTE_PATHS` and the row is
 * rendered as plain text if the path is not registered, so a typo or a
 * deleted route degrades to a readable statement instead of a link that
 * navigates nowhere.
 *
 * Severity drives order and carries a text label, never colour alone. A
 * reviewer who cannot distinguish the amber from the red still reads
 * "Critical" and "Scheduled".
 */

const SEVERITY_ORDER: Record<ActionSeverity, number> = {
  critical: 0,
  attention: 1,
  scheduled: 2,
};

const SEVERITY_LABEL_KEY: Record<ActionSeverity, StringKey> = {
  critical: 'dashboard.action.severity.critical',
  attention: 'dashboard.action.severity.attention',
  scheduled: 'dashboard.action.severity.scheduled',
};

const SEVERITY_CLASS: Record<ActionSeverity, string> = {
  critical: 'border-red-200 bg-red-50 text-red-700',
  attention: 'border-amber-200 bg-amber-50 text-amber-700',
  scheduled: 'border-line-200 bg-tint-100 text-gray-600',
};

/** A path is offered as a link only if the router actually declares it. */
function isRegisteredRoute(path: string): boolean {
  return PROTECTED_ROUTE_PATHS.includes(path);
}

export function ActionCentre({ actions }: { actions: readonly EvidenceAction[] }) {
  const { t } = useLocale();

  if (actions.length === 0) {
    return (
      <p className="py-5 text-center text-meta text-gray-600">
        {t('dashboard.action.empty')}
      </p>
    );
  }

  const ordered = [...actions].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  );

  return (
    <ul className="divide-y divide-line-200">
      {ordered.map((action) => {
        const title = t(action.titleKey as StringKey);
        const detail = t(action.detailKey as StringKey);
        const registered = isRegisteredRoute(action.route);

        const body = (
          <>
            <span className="flex min-w-0 flex-col gap-1">
              <span className="flex flex-wrap items-center gap-2">
                <span
                  className={cn(
                    'rounded-full border px-2 py-0.5 text-caption font-bold',
                    SEVERITY_CLASS[action.severity],
                  )}
                >
                  {t(SEVERITY_LABEL_KEY[action.severity])}
                </span>
                <span className="text-body font-semibold text-forest-900">{title}</span>
                {action.count !== null && (
                  <span className="text-caption font-bold text-gray-600" dir="ltr">
                    {action.count}
                  </span>
                )}
              </span>
              <span className="text-caption text-gray-600">{detail}</span>
            </span>
            {registered && (
              <Icon
                name="analysis"
                size={16}
                className="mt-1 shrink-0 text-gray-400 transition-colors group-hover:text-forest-900"
              />
            )}
          </>
        );

        return (
          <li key={action.id}>
            {registered ? (
              <Link
                to={action.route}
                className="group flex items-start justify-between gap-3 px-1 py-3 transition-colors hover:bg-tint-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
              >
                {body}
              </Link>
            ) : (
              // Unreachable with the shipped fixtures; kept so a future
              // action with a bad path cannot become a dead control.
              <div className="flex items-start justify-between gap-3 px-1 py-3">{body}</div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
