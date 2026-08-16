import type { ReactNode } from 'react';

/**
 * Minimal page frame for the one state that has to render without the
 * authenticated shell: a signed-out visitor on a URL that does not exist.
 *
 * It reuses the product surface (`app-atmosphere`, paper background, the
 * same centered content column the empty-state pattern expects) rather than
 * introducing a second visual language — there is no rail or context bar to
 * show a visitor who has no session.
 */
export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-atmosphere flex min-h-screen items-center justify-center bg-paper-50 px-4 py-10">
      <main className="w-full max-w-xl">{children}</main>
    </div>
  );
}
