const FORMATTER = new Intl.DateTimeFormat('en-GB', {
  day: '2-digit',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
});

/** Formats a backend ISO datetime string for display — deliberately
 * locale-invariant (not re-formatted per `en`/`ar`): a timestamp is a
 * technical/numeric value, not translatable UI copy, and must never be
 * bidi-reversed in RTL (§ accessibility/RTL requirements) — callers render
 * the result inside a `dir="ltr"` element for that reason. Falls back to
 * the raw string for anything that doesn't parse, rather than showing
 * "Invalid Date". */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return FORMATTER.format(date);
}
