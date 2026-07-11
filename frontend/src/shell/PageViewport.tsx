import type { ReactNode } from 'react';

/** §14.3 global layout: the `main` landmark, 12-col grid rhythm, and the
 * 1376px content max-width — the one wrapper every authenticated route
 * renders inside. Individual pages set their own single `h1` (via
 * PageHeader) inside this region. */
export function PageViewport({ children }: { children: ReactNode }) {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="mx-auto w-full max-w-[var(--content-max)] px-4 py-6 md:px-6 xl:px-8 xl:py-8"
    >
      {children}
    </main>
  );
}
