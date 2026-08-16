/** The id of a single tab button — shared by `Tabs` and `TabPanel` so the
 * `aria-controls`/`aria-labelledby` pair can never drift apart. Kept out of
 * `Tabs.tsx` so that file only exports components (React Fast Refresh). */
export function tabButtonId(id: string, value: string): string {
  return `${id}-tab-${value}`;
}
