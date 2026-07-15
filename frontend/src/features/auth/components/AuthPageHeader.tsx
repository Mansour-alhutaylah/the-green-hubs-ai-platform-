import type { ReactNode } from 'react';

export interface AuthPageHeaderProps {
  eyebrow: string;
  heading: string;
  supporting?: ReactNode;
  /** Tighter bottom margin for pages whose form sits closer beneath the
   * heading (currently just Login) — the default spacing stays the shared
   * value for the other 6 auth pages. */
  spacing?: 'default' | 'compact';
}

/**
 * The shared heading pattern across all 7 auth pages (approved redesign):
 * a quiet uppercase eyebrow, the page's single heading, and an optional
 * supporting sentence — one definition instead of each page re-laying it
 * out. Reuses the existing `.type-label` treatment (RTL-safe: uppercase +
 * tracking in LTR, weight-only in Arabic) and the `display` type token for
 * a heading with real presence without introducing a new size.
 */
export function AuthPageHeader({
  eyebrow,
  heading,
  supporting,
  spacing = 'default',
}: AuthPageHeaderProps) {
  return (
    <div className={spacing === 'compact' ? 'mb-4 sm:mb-5' : 'mb-6 sm:mb-8'}>
      <p className="type-label mb-3 flex items-center gap-2 text-leaf-700">
        <span className="h-1.5 w-1.5 rounded-full bg-leaf-500" aria-hidden />
        {eyebrow}
      </p>
      <h1 className="max-w-[18ch] text-display text-forest-900 sm:text-hero">{heading}</h1>
      {supporting && (
        <p className="mt-3 max-w-[42ch] break-words text-body leading-6 text-gray-600" data-user-content>
          {supporting}
        </p>
      )}
    </div>
  );
}
