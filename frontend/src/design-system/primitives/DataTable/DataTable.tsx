import type { ReactNode } from 'react';
import { cn } from '@/lib/utils/cn';

/**
 * The shared tabular listing.
 *
 * A real `<table>`, not a grid of `<div>`s. The existing list pages render
 * `<ul>` of links styled into columns, which looks like a table and is not
 * one: a screen-reader user gets no column headers, no row/column count,
 * and none of the table navigation commands their software provides. F2A's
 * listings are genuinely tabular data, so they use the element for it.
 *
 * What that buys, concretely:
 *
 * - `<caption>` names the table. It is visually hidden by default (the
 *   surrounding `SectionCard` already shows a heading) but always present,
 *   so the table is never anonymous in a list of landmarks.
 * - `scope="col"` on every header, and one column marked `isRowHeader`
 *   rendered as `<th scope="row">` — that cell becomes each row's
 *   announced name, so navigating down a column says "Facility Alpha,
 *   Status, Active" rather than just "Active".
 * - Narrow screens scroll the table inside its own container rather than
 *   pushing the page sideways. A horizontally scrolling *page* is the
 *   failure mode; a horizontally scrolling *table* is the fix. The
 *   container takes `tabIndex={0}` so it is reachable by keyboard, which
 *   is required for any scrollable region.
 */

export interface DataTableColumn<Row> {
  id: string;
  header: string;
  cell: (row: Row) => ReactNode;
  /**
   * Renders this column's cell as `<th scope="row">` — the row's
   * accessible name. Exactly one column should set it.
   */
  isRowHeader?: boolean;
  /** Applied to both the header and body cells of this column. */
  className?: string;
  /** Hides the column below the `md` breakpoint, for detail that is
   * genuinely secondary. Its content must also appear somewhere in the row
   * header's cell, or it is simply lost on a phone. */
  secondary?: boolean;
}

export interface DataTableProps<Row> {
  /** The table's accessible name. */
  caption: string;
  /** Render the caption visibly rather than for assistive tech only. */
  captionVisible?: boolean;
  columns: readonly DataTableColumn<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  /** Shown in place of the body when there are no rows. A table with a
   * stated "no matching rows" beats an empty grid with no explanation. */
  emptyMessage: string;
  className?: string;
}

export function DataTable<Row>({
  caption,
  captionVisible = false,
  columns,
  rows,
  rowKey,
  emptyMessage,
  className,
}: DataTableProps<Row>) {
  return (
    <section
      // Keyboard-reachable because it scrolls: a scroll container that
      // cannot be focused is unusable without a pointer (WCAG 2.1.1 —
      // there would be no way to reach the columns hidden off the edge).
      // A named `<section>` is already the region landmark, so no `role`
      // is needed. The lint rule's general advice — never put `tabIndex`
      // on a non-interactive element — is right everywhere except a
      // scrollable region, which is the documented exception.
      // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
      aria-label={caption}
      className={cn(
        'w-full overflow-x-auto focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700',
        className,
      )}
    >
      <table className="w-full min-w-[36rem] border-collapse text-start">
        <caption
          className={cn(
            captionVisible ? 'px-4 py-3 text-start text-meta text-gray-600 sm:px-5' : 'sr-only',
          )}
        >
          {caption}
        </caption>
        <thead>
          <tr className="border-b border-line-200 bg-mist-50">
            {columns.map((column) => (
              <th
                key={column.id}
                scope="col"
                className={cn(
                  'px-4 py-3 text-start text-caption font-bold text-gray-600 sm:px-5',
                  column.secondary && 'hidden md:table-cell',
                  column.className,
                )}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line-200">
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-4 py-8 text-center text-meta text-gray-600 sm:px-5"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={rowKey(row)} className="transition-colors hover:bg-mist-50">
                {columns.map((column) => {
                  const content = column.cell(row);
                  const cellClassName = cn(
                    'px-4 py-3 align-middle text-meta text-gray-600 sm:px-5',
                    column.secondary && 'hidden md:table-cell',
                    column.className,
                  );
                  return column.isRowHeader ? (
                    <th
                      key={column.id}
                      scope="row"
                      className={cn(cellClassName, 'text-start font-bold text-ink-900')}
                    >
                      {content}
                    </th>
                  ) : (
                    <td key={column.id} className={cellClassName}>
                      {content}
                    </td>
                  );
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </section>
  );
}

/**
 * A skeleton shaped like the table it stands in for, so the row area does
 * not collapse and then jump when data lands.
 *
 * Presentational only: the surrounding `StateBlock` owns the `<output>`
 * that announces the busy state, so this contributes nothing to the
 * accessibility tree.
 */
export function DataTableSkeleton({
  columns,
  rows = 5,
  className,
}: {
  columns: number;
  rows?: number;
  className?: string;
}) {
  return (
    <span aria-hidden className={cn('block w-full', className)}>
      <span className="flex gap-4 border-b border-line-200 bg-mist-50 px-4 py-3 sm:px-5">
        {Array.from({ length: columns }, (_unusedHeader, index) => (
          <span key={index} className="loading-skeleton block h-3 flex-1 rounded-s" />
        ))}
      </span>
      {Array.from({ length: rows }, (_unusedRow, rowIndex) => (
        <span
          key={rowIndex}
          className="flex gap-4 border-b border-line-200 px-4 py-4 last:border-b-0 sm:px-5"
        >
          {Array.from({ length: columns }, (_unusedCell, index) => (
            <span key={index} className="loading-skeleton block h-3.5 flex-1 rounded-s" />
          ))}
        </span>
      ))}
    </span>
  );
}
