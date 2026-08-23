import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';
import { EmptyState } from '../EmptyState/EmptyState';
import { LoadingDiamond } from '../LoadingDiamond/LoadingDiamond';

/**
 * The one rendering of a non-populated data state.
 *
 * Every F2A page reads a `DataState`/`ResourceState` and hands the
 * non-`ready` case to this component, so "we're loading", "there is
 * nothing here", "we couldn't find out", "you may not see this", "that
 * doesn't exist", and "this capability isn't built" look and read as six
 * distinct things across the whole product instead of collapsing into one
 * grey box per page.
 *
 * The distinctions are the point. An error rendered as an empty state
 * tells a person their workspace is empty when it is not; an unavailable
 * capability rendered as an error tells them something broke when nothing
 * did. The component takes the status as a closed union precisely so a
 * caller cannot blur them.
 *
 * Announcement follows the same split:
 *
 * - `loading` renders inside `<output>` (an implicit `role="status"`,
 *   polite), so a screen reader is told the region is busy without having
 *   the current reading interrupted.
 * - `error` and `forbidden` render with `role="alert"` (assertive) —
 *   these are the outcomes a person must hear about, because they change
 *   what they can do next.
 * - `empty`, `not-found`, and `unavailable` are ordinary content: they are
 *   the settled answer, not an interruption.
 */

export type StateBlockStatus =
  | 'loading'
  | 'empty'
  | 'error'
  | 'forbidden'
  | 'not-found'
  | 'unavailable';

export interface StateBlockProps {
  status: StateBlockStatus;
  title: string;
  description?: string;
  /** Typically a retry button for `error`, or a link out for `empty`. */
  action?: ReactNode;
  /**
   * Shown instead of the spinner while `loading` — a skeleton shaped like
   * the content being awaited, which keeps the layout from jumping when
   * the real rows land.
   */
  loadingSkeleton?: ReactNode;
  /** Accessible label for the busy region. Required for `loading`. */
  loadingLabel?: string;
  className?: string;
}

export function StateBlock({
  status,
  title,
  description,
  action,
  loadingSkeleton,
  loadingLabel,
  className,
}: StateBlockProps) {
  if (status === 'loading') {
    return (
      <output
        aria-label={loadingLabel ?? title}
        aria-busy="true"
        className={cn('block w-full', className)}
      >
        {loadingSkeleton ?? (
          <span className="flex flex-col items-center gap-3 py-12">
            <LoadingDiamond size={40} />
            <span className="text-meta text-gray-600">{title}</span>
          </span>
        )}
      </output>
    );
  }

  const isAlert = status === 'error' || status === 'forbidden';

  return (
    <div
      role={isAlert ? 'alert' : undefined}
      data-state={status}
      className={cn('w-full', className)}
    >
      <EmptyState title={title} description={description} action={action} />
    </div>
  );
}

/**
 * The partial-coverage banner: some of what this screen asks for resolved
 * and some did not.
 *
 * Deliberately *not* a `StateBlock` status — partial content is still
 * content, so it renders above the real rows rather than replacing them.
 * `role="status"` announces the caveat politely once the region settles.
 */
export function PartialCoverageNotice({
  message,
  className,
}: {
  message: string;
  className?: string;
}) {
  return (
    <output
      className={cn(
        'mb-4 block rounded-m border border-amber-100 bg-amber-100 px-3 py-2 text-meta font-semibold text-amber-700',
        className,
      )}
    >
      {message}
    </output>
  );
}
