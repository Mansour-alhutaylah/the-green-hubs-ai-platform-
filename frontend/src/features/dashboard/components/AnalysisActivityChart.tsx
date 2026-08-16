import { useMemo, useState } from 'react';
import { Tabs, TabPanel } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import type { DashboardActivityPoint } from '@/lib/data/contracts';

const MONTH_KEYS: readonly StringKey[] = [
  'dashboard.chart.month.jan',
  'dashboard.chart.month.feb',
  'dashboard.chart.month.mar',
  'dashboard.chart.month.apr',
  'dashboard.chart.month.may',
  'dashboard.chart.month.jun',
  'dashboard.chart.month.jul',
  'dashboard.chart.month.aug',
  'dashboard.chart.month.sep',
  'dashboard.chart.month.oct',
  'dashboard.chart.month.nov',
  'dashboard.chart.month.dec',
];

const QUARTER_KEYS: readonly StringKey[] = [
  'dashboard.chart.quarter.q1',
  'dashboard.chart.quarter.q2',
  'dashboard.chart.quarter.q3',
  'dashboard.chart.quarter.q4',
];

const WIDTH = 560;
const HEIGHT = 200;
const PAD_X = 8;
const PAD_TOP = 12;
const PAD_BOTTOM = 28;

const TABS_ID = 'analysis-activity-period';
const PANEL_ID = 'analysis-activity-panel';

type Period = 'monthly' | 'quarterly';

/**
 * Hand-rolled SVG line/area chart — no charting dependency. Monthly is the
 * source series; Quarterly sums that same series into 4 buckets, so the
 * toggle is a real derived view rather than a second dataset.
 *
 * The series arrives as domain data (`month` 1–12 plus a count); the month
 * label is looked up here, because a stored label would be a translation
 * baked into data.
 */
export function AnalysisActivityChart({ series }: { series: readonly DashboardActivityPoint[] }) {
  const { t } = useLocale();
  const [period, setPeriod] = useState<Period>('monthly');
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const points = useMemo(() => {
    const byMonth = [...series].sort((a, b) => a.month - b.month);
    if (period === 'monthly') {
      return byMonth.map((entry) => ({
        labelKey: MONTH_KEYS[entry.month - 1] ?? MONTH_KEYS[0]!,
        value: entry.completedRuns,
      }));
    }
    return QUARTER_KEYS.map((labelKey, quarterIndex) => ({
      labelKey,
      value: byMonth
        .filter((entry) => Math.ceil(entry.month / 3) === quarterIndex + 1)
        .reduce((total, entry) => total + entry.completedRuns, 0),
    }));
  }, [series, period]);

  const maxValue = Math.max(1, ...points.map((point) => point.value));
  const plotWidth = WIDTH - PAD_X * 2;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const coords = points.map((point, index) => {
    const x = PAD_X + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
    const y = PAD_TOP + plotHeight - (point.value / maxValue) * plotHeight;
    return { ...point, x, y };
  });

  const gridLines = [0.25, 0.5, 0.75, 1];

  function handleMove(event: React.MouseEvent<SVGSVGElement>) {
    const svg = event.currentTarget;
    const rect = svg.getBoundingClientRect();
    const relativeX = ((event.clientX - rect.left) / rect.width) * WIDTH;
    let nearest = 0;
    let nearestDistance = Infinity;
    coords.forEach((c, index) => {
      const distance = Math.abs(c.x - relativeX);
      if (distance < nearestDistance) {
        nearestDistance = distance;
        nearest = index;
      }
    });
    setHoverIndex(nearest);
  }

  const hovered = hoverIndex != null ? coords[hoverIndex] : undefined;

  if (coords.length === 0) {
    return <p className="py-6 text-center text-meta text-gray-600">{t('dashboard.queue.empty')}</p>;
  }

  const linePath = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x},${c.y}`).join(' ');
  const areaPath = `${linePath} L${coords.at(-1)!.x},${PAD_TOP + plotHeight} L${coords[0]!.x},${PAD_TOP + plotHeight} Z`;

  return (
    <div>
      <Tabs<Period>
        id={TABS_ID}
        panelId={PANEL_ID}
        className="mb-3 justify-end"
        label={t('dashboard.section.analysisActivity')}
        value={period}
        onChange={(next) => {
          setPeriod(next);
          setHoverIndex(null);
        }}
        items={[
          { value: 'monthly', label: t('dashboard.chart.monthly') },
          { value: 'quarterly', label: t('dashboard.chart.quarterly') },
        ]}
      />

      <TabPanel id={PANEL_ID} tabsId={TABS_ID} value={period} focusable>
        <div className="relative">
          <svg
            viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
            className="w-full touch-none"
            aria-label={t('dashboard.section.analysisActivity')}
            onMouseMove={handleMove}
            onMouseLeave={() => setHoverIndex(null)}
          >
            {gridLines.map((fraction) => (
              <line
                key={fraction}
                x1={PAD_X}
                x2={WIDTH - PAD_X}
                y1={PAD_TOP + plotHeight * (1 - fraction)}
                y2={PAD_TOP + plotHeight * (1 - fraction)}
                stroke="var(--color-line-200)"
                strokeWidth={1}
              />
            ))}

            <defs>
              <linearGradient id="analysis-activity-fill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-chart-accent-2)" stopOpacity={0.28} />
                <stop offset="100%" stopColor="var(--color-chart-accent-2)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <path d={areaPath} fill="url(#analysis-activity-fill)" stroke="none" />
            <path
              d={linePath}
              fill="none"
              stroke="var(--color-chart-accent-1)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />

            {hovered && (
              <line
                x1={hovered.x}
                x2={hovered.x}
                y1={PAD_TOP}
                y2={PAD_TOP + plotHeight}
                stroke="var(--color-line-300)"
                strokeWidth={1}
                strokeDasharray="3 3"
              />
            )}
            {coords.map((c, index) => (
              <circle
                key={c.labelKey}
                cx={c.x}
                cy={c.y}
                r={index === hoverIndex ? 5 : index === coords.length - 1 ? 4 : 0}
                fill="var(--color-chart-accent-1)"
                stroke="var(--color-surface-0)"
                strokeWidth={2}
              />
            ))}

            {coords.map((c) => (
              <text
                key={c.labelKey}
                x={c.x}
                y={HEIGHT - 8}
                textAnchor="middle"
                className="fill-gray-600"
                style={{ fontSize: 10 }}
              >
                {t(c.labelKey)}
              </text>
            ))}
          </svg>

          {hovered && (
            <div
              className="pointer-events-none absolute top-0 rounded-m border border-line-200 bg-surface-0 px-2.5 py-1.5 text-caption shadow-float"
              style={{
                left: `${(hovered.x / WIDTH) * 100}%`,
                transform: 'translate(-50%, -110%)',
              }}
            >
              <p className="font-bold text-forest-900">{hovered.value}</p>
              <p className="text-gray-600">{t(hovered.labelKey)}</p>
            </div>
          )}
        </div>

        <table className="sr-only">
          <caption>{t('dashboard.section.analysisActivity')}</caption>
          <tbody>
            {points.map((point) => (
              <tr key={point.labelKey}>
                <th scope="row">{t(point.labelKey)}</th>
                <td>{point.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </TabPanel>
    </div>
  );
}
