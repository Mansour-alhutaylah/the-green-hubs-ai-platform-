import { Icon } from '../Icon/Icon';
import { cn } from '@/lib/utils/cn';

export interface PaginationProps {
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
  /** Pre-formatted, already-translated summary text, e.g. "Showing 1–5 of 9". */
  summary: string;
  previousLabel: string;
  nextLabel: string;
}

/** Shared page-number strip used by every list page with more rows than fit
 * on one screen. The summary always renders (so the count is visible even
 * on a single page); only the page-number navigation hides itself when
 * there's nothing to navigate to. Deliberately translation-agnostic —
 * callers pass already localized label strings. */
export function Pagination({ page, pageCount, onPageChange, summary, previousLabel, nextLabel }: PaginationProps) {
  return (
    <div className="flex flex-col items-center justify-between gap-3 border-t border-line-200 px-4 py-3 sm:flex-row sm:px-5">
      <p className="text-caption text-gray-600">{summary}</p>
      {pageCount > 1 && (
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            aria-label={previousLabel}
            className="flex h-8 w-8 items-center justify-center rounded-m text-gray-600 transition-colors hover:bg-tint-100 hover:text-forest-900 disabled:pointer-events-none disabled:opacity-40"
          >
            <Icon name="chevron-left" size={16} />
          </button>
          {Array.from({ length: pageCount }, (_, index) => index + 1).map((pageNumber) => (
            <button
              key={pageNumber}
              type="button"
              onClick={() => onPageChange(pageNumber)}
              aria-current={pageNumber === page ? 'page' : undefined}
              className={cn(
                'flex h-8 min-w-8 items-center justify-center rounded-m px-2 text-meta font-bold transition-colors',
                pageNumber === page
                  ? 'bg-forest-900 text-white'
                  : 'text-gray-600 hover:bg-tint-100 hover:text-forest-900',
              )}
            >
              {pageNumber}
            </button>
          ))}
          <button
            type="button"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= pageCount}
            aria-label={nextLabel}
            className="flex h-8 w-8 items-center justify-center rounded-m text-gray-600 transition-colors hover:bg-tint-100 hover:text-forest-900 disabled:pointer-events-none disabled:opacity-40"
          >
            <Icon name="chevron-right" size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
