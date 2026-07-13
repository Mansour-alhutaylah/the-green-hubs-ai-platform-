import { Icon, PopoverMenu } from '@/design-system';
import { NotificationsPanel } from './NotificationsPanel';

/** §3.2: bell + unread badge (0 in Phase 1 — no real notification feed
 * exists yet) → 420px panel overlay. */
export function NotificationsBell() {
  return (
    <PopoverMenu
      trigger={
        <button
          type="button"
          aria-label="Notifications"
          className="relative flex h-10 w-10 items-center justify-center rounded-m text-gray-600 transition-colors hover:bg-mist-50 hover:text-forest-900"
        >
          <Icon name="bell" size={20} />
        </button>
      }
    >
      <NotificationsPanel />
    </PopoverMenu>
  );
}
