import { useMemo, useState } from 'react';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';
import { MONTHLY_ANALYSIS_ACTIVITY } from '../mockDashboardData';

const QUARTER_KEYS = [
  'dashboard.chart.quarter.q1',
  'dashboard.chart.quarter.q2',
  'dashboard.chart.quarter.q3',
  'dashboard.chart.quarter.q4',
] as const;

const WIDTH = 560;
const HEIGHT = 200;
const PAD_X = 8;
const PAD_TOP = 12;
const PAD_BOTTOM = 28;

/** Hand-rolled SVG line/area chart — no charting dependency. Monthly is the
 * source series; Quarterly sums that same series into 4 buckets, so the
 * toggle is a real derived view rather than a second fabricated dataset. */
export function AnalysisActivityChart() {
  const { t } = useLocale();
  const [period, setPeriod] = useState<'monthly' | 'quarterly'>('monthly');
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  const points = useMemo(() => {
    if (period === 'monthly') {
      return MONTHLY_ANALYSIS_ACTIVITY.map((entry) => ({ labelKey: entry.monthKey, value: entry.value }));
    }
    return QUARTER_KEYS.map((labelKey, quarterIndex) => {
      const months = MONTHLY_ANALYSIS_ACTIVITY.slice(quarterIndex * 3, quarterIndex * 3 + 3);
      return { labelKey, value: months.reduce((total, month) => total + month.value, 0) };
    });
  }, [period]);

  const maxValue = Math.max(...points.map((point) => point.value));
  const plotWidth = WIDTH - PAD_X * 2;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;

  const coords = points.map((point, index) => {
    const x = PAD_X + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
    const y = PAD_TOP + plotHeight - (point.value / maxValue) * plotHeight;
    return { ...point, x, y };
  });

  const linePath = coords.map((c, i) => `${i === 0 ? 'M' : 'L'}${c.x},${c.y}`).join(' ');
  const areaPath = `${linePath} L${coords.at(-1)!.x},${PAD_TOP + plotHeight} L${coords[0]!.x},${PAD_TOP + plotHeight} Z`;
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

  return (
    <div>
      <div className="mb-3 flex items-center justify-end gap-1" role="tablist" aria-label={t('dashboard.section.analysisActivity')}>
        {(['monthly', 'quarterly'] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={period === value}
            onClick={() => {
              setPeriod(value);
              setHoverIndex(null);
            }}
            className={cn(
              'rounded-m px-3 py-1.5 text-caption font-bold transition-colors',
              period === value
                ? 'bg-forest-900 text-white'
                : 'text-gray-600 hover:bg-tint-100 hover:text-forest-900',
            )}
          >
            {t(value === 'monthly' ? 'dashboard.chart.monthly' : 'dashboard.chart.quarterly')}
          </button>
        ))}
      </div>

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
          <path d={linePath} fill="none" stroke="var(--color-chart-accent-1)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />

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
    </div>
  );
}
