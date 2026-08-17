import type { EvidenceThroughputPoint } from '@/lib/data/contracts';
import { useLocale } from '@/lib/i18n/useLocale';

/**
 * The dashboard's one dominant visual: evidence reaching verified and
 * report-ready, by month.
 *
 * Deliberately a single chart. An earlier layout carried a bar chart and a
 * donut side by side, which split attention without adding a second
 * question worth answering. One trend, read left to right, is the thing an
 * executive actually wants from a dashboard.
 *
 * It is a plain inline SVG built from the data, not a charting dependency,
 * because the shape is two polylines over a labelled grid and adding a
 * library for that would be weight without benefit.
 *
 * Accessibility is the load-bearing part. The SVG is `aria-hidden`, and
 * the real content is a visually hidden table plus a one-sentence summary
 * that states the period, the units, and the direction of travel. A screen
 * reader gets the numbers, not a shrug. Axis ticks and units are rendered
 * visibly too, so the chart is readable without hovering anything: there
 * are no tooltips to discover, because a tooltip-only figure is invisible
 * on a touch device.
 */
export function EvidenceThroughputChart({
  points,
  period,
}: {
  points: readonly EvidenceThroughputPoint[];
  period: string;
}) {
  const { t } = useLocale();

  if (points.length === 0) {
    return (
      <p className="py-6 text-center text-meta text-gray-600">
        {t('dashboard.throughput.empty')}
      </p>
    );
  }

  const width = 640;
  const height = 200;
  const padding = { top: 12, right: 12, bottom: 26, left: 34 };

  const maxValue = Math.max(
    1,
    ...points.map((point) => Math.max(point.verified, point.reportReady)),
  );
  // Round the axis up to a clean step so the gridline labels are readable
  // integers rather than whatever the maximum happened to be.
  const step = maxValue <= 5 ? 1 : maxValue <= 20 ? 5 : 10;
  const axisMax = Math.ceil(maxValue / step) * step;

  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  const x = (index: number) =>
    padding.left +
    (points.length === 1 ? plotWidth / 2 : (index * plotWidth) / (points.length - 1));
  const y = (value: number) => padding.top + plotHeight - (value / axisMax) * plotHeight;

  const line = (key: 'verified' | 'reportReady') =>
    points.map((point, index) => `${x(index)},${y(point[key])}`).join(' ');

  const ticks = Array.from({ length: axisMax / step + 1 }, (_, index) => index * step);

  const totalVerified = points.reduce((sum, point) => sum + point.verified, 0);
  const totalReportReady = points.reduce((sum, point) => sum + point.reportReady, 0);

  const summary = t('dashboard.throughput.summary', {
    period,
    months: points.length,
    verified: totalVerified,
    reportReady: totalReportReady,
    first: points[0]?.month ?? '',
    last: points[points.length - 1]?.month ?? '',
  });

  return (
    // No `useId` anywhere in this component. The Preview dashboard is
    // asserted to render byte-identically across two mounts, and a
    // generated id differs between them, so an id here would make the
    // page non-deterministic for the sake of a label the visually hidden
    // caption and table already provide.
    <figure className="m-0">
      <figcaption className="sr-only">{t('dashboard.throughput.title')}</figcaption>

      {/* Legend is real text, not colour alone. */}
      <ul className="mb-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-caption text-gray-600">
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full bg-forest-700" aria-hidden />
          {t('dashboard.throughput.series.verified')}
        </li>
        <li className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 rounded-full bg-leaf-500" aria-hidden />
          {t('dashboard.throughput.series.reportReady')}
        </li>
        <li className="ms-auto">{t('dashboard.throughput.unit')}</li>
      </ul>

      <div className="overflow-x-auto">
        {/* Hidden from assistive technology on purpose: the equivalent
            content is the summary sentence and the table below, which
            carry the actual numbers rather than a shape. */}
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-50 w-full min-w-[420px]"
          aria-hidden
          focusable="false"
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={y(tick)}
                y2={y(tick)}
                className="stroke-line-200"
                strokeWidth={1}
              />
              <text
                x={padding.left - 7}
                y={y(tick) + 3.5}
                textAnchor="end"
                className="fill-gray-500 text-[10px]"
              >
                {tick}
              </text>
            </g>
          ))}

          <polyline
            points={line('verified')}
            fill="none"
            className="stroke-forest-700"
            strokeWidth={2.25}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          <polyline
            points={line('reportReady')}
            fill="none"
            className="stroke-leaf-500"
            strokeWidth={2.25}
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {points.map((point, index) => (
            <g key={point.month}>
              <circle cx={x(index)} cy={y(point.verified)} r={3} className="fill-forest-700" />
              <circle cx={x(index)} cy={y(point.reportReady)} r={3} className="fill-leaf-500" />
              <text
                x={x(index)}
                y={height - 8}
                textAnchor="middle"
                className="fill-gray-500 text-[10px]"
              >
                {point.month}
              </text>
            </g>
          ))}
        </svg>
      </div>

      {/* The accessible equivalent: a real table, plus the sentence a
          sighted reader gets from the shape of the lines. */}
      <p className="mt-3 text-caption text-gray-600">{summary}</p>
      <table className="sr-only">
        <caption>{t('dashboard.throughput.title')}</caption>
        <thead>
          <tr>
            <th scope="col">{t('dashboard.throughput.axis.month')}</th>
            <th scope="col">{t('dashboard.throughput.series.verified')}</th>
            <th scope="col">{t('dashboard.throughput.series.reportReady')}</th>
          </tr>
        </thead>
        <tbody>
          {points.map((point) => (
            <tr key={point.month}>
              <th scope="row">{point.month}</th>
              <td>{point.verified}</td>
              <td>{point.reportReady}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
