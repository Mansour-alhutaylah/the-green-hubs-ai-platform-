import type { ReactNode } from 'react';

export interface AuthPageHeaderProps {
  eyebrow: string;
  heading: string;
  supporting?: ReactNode;
}

/**
 * The shared heading pattern across all 7 auth pages (approved redesign):
 * a quiet uppercase eyebrow, the page's single heading, and an optional
 * supporting sentence — one definition instead of each page re-laying it
 * out. Reuses the existing `.type-label` treatment (RTL-safe: uppercase +
 * tracking in LTR, weight-only in Arabic) and the `display` type token for
 * a heading with real presence without introducing a new size.
 */
export function AuthPageHeader({ eyebrow, heading, supporting }: AuthPageHeaderProps) {
  return (
    <div className="mb-8">
      <p className="type-label mb-3 text-gray-600">{eyebrow}</p>
      <h1 className="text-display text-forest-900">{heading}</h1>
      {supporting && (
        <p className="mt-2.5 max-w-[42ch] text-body text-gray-600">{supporting}</p>
      )}
    </div>
  );
}
