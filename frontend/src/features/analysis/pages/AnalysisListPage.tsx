import { Link } from 'react-router';
import {
  DemoDataBadge,
  EmptyState,
  Icon,
  LoadingSkeleton,
  SectionCard,
} from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';
import { cn } from '@/lib/utils/cn';
import { MOCK_ANALYSIS_RUNS, type AnalysisRunStatus } from '../mockAnalysisData';
import { AnalysisStatusBadge } from '../components/AnalysisStatusBadge';

const STATUS_RAIL: Record<AnalysisRunStatus, string> = {
  COMPLETE: 'bg-leaf-500',
  PROCESSING: 'bg-sky-700',
  FAILED: 'bg-red-700',
};

const STATUS_CONTEXT: Record<AnalysisRunStatus, string> = {
  COMPLETE: 'Sample result ready for human review',
  PROCESSING: 'Sample processing state · No AI service running',
  FAILED: 'Controlled preview failure · No provider contacted',
};

export function AnalysisListPage() {
  const { t } = useLocale();
  const completeRuns = MOCK_ANALYSIS_RUNS.filter((run) => run.status === 'COMPLETE');
  const averageConfidence = Math.round(
    completeRuns.reduce((total, run) => total + (run.confidence ?? 0), 0) /
      Math.max(completeRuns.length, 1),
  );

  return (
    <div>
      <PageHeader
        eyebrow="Intelligence workspace"
        title={t('nav.analysis')}
        subtitle="Review sample analysis journeys and source handling without invoking an AI service."
        action={<DemoDataBadge label="Sample data · Analysis preview" />}
      />

      <dl className="mb-5 grid gap-3 sm:grid-cols-3">
        <AnalysisMetric
          icon="analysis"
          label="Sample runs"
          value={String(MOCK_ANALYSIS_RUNS.length)}
          detail="Across all preview states"
        />
        <AnalysisMetric
          icon="frameworks"
          label="Illustrative confidence"
          value={`${averageConfidence}%`}
          detail="Completed sample only"
        />
        <AnalysisMetric
          icon="shield-check"
          label="Review posture"
          value="Human-led"
          detail="No evidence is verified"
        />
      </dl>

      <SectionCard
        className="rounded-xl border-leaf-300/60"
        title="Recent analysis runs"
        description="Source relationship, confidence, and current sample state remain visible together."
        contentClassName="p-3 sm:p-4"
      >
        <ul className="space-y-3" aria-label="Sample analysis runs">
          {MOCK_ANALYSIS_RUNS.map((run, index) => (
            <li key={run.id}>
              <Link
                to={`/analysis/${run.id}`}
                className={cn(
                  'surface-lift group relative grid gap-4 overflow-hidden rounded-xl border bg-surface-0 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center',
                  index === 0 ? 'border-leaf-300 shadow-raise' : 'border-line-200',
                )}
              >
                <span className={cn('absolute inset-y-2 start-0 w-1 rounded-e-full', STATUS_RAIL[run.status])} aria-hidden />
                <span className="flex min-w-0 items-start gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-l border border-leaf-300 bg-mist-50 text-leaf-700" aria-hidden>
                    <Icon name="analysis" size={20} />
                  </span>
                  <span className="min-w-0">
                    <span className="type-label block text-gray-600">Source document</span>
                    <span className="mt-0.5 block truncate text-body font-bold text-ink-900 transition-colors group-hover:text-leaf-700" data-user-content>
                      {run.documentName}
                    </span>
                    <span className="mt-1 block text-caption text-gray-600">
                      Started {run.startedAt} · {STATUS_CONTEXT[run.status]}
                    </span>
                  </span>
                </span>

                <span className="flex min-w-40 flex-col items-start gap-2 sm:items-end">
                  <AnalysisStatusBadge status={run.status} />
                  {run.confidence != null && (
                    <span className="w-full sm:w-40">
                      <span className="flex items-center justify-between gap-2 text-caption font-semibold text-gray-600">
                        <span>Sample confidence</span>
                        <span>{run.confidence}%</span>
                      </span>
                      <progress
                        className="sr-only"
                        aria-label={`${run.documentName} sample confidence`}
                        max={100}
                        value={run.confidence}
                      >
                        {run.confidence}%
                      </progress>
                      <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-line-200" aria-hidden>
                        <span
                          className="block h-full rounded-full bg-leaf-500"
                          style={{ width: `${run.confidence}%` }}
                        />
                      </span>
                    </span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </SectionCard>

      <section className="mt-5" aria-labelledby="analysis-state-preview-heading">
        <div className="mb-3">
          <p className="type-label text-leaf-700">Interface states</p>
          <h2 id="analysis-state-preview-heading" className="mt-1 text-panel text-forest-900">
            Workflow state preview
          </h2>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <SectionCard className="rounded-xl bg-mist-50">
            <EmptyState
              title="No analysis yet"
              description="A connected workflow will show eligible documents here."
              className="py-5"
            />
          </SectionCard>
          <SectionCard className="rounded-xl border-leaf-300/60 bg-mist-50" aria-live="polite">
            <p className="mb-3 text-meta font-bold text-forest-900">Sample processing</p>
            <LoadingSkeleton lines={4} label="Sample analysis is processing" />
          </SectionCard>
          <SectionCard className="rounded-xl bg-tint-100">
            <EmptyState
              title="Analysis not available"
              description="Unsupported files remain visible with a clear reason."
              className="py-5"
            />
          </SectionCard>
        </div>
      </section>
    </div>
  );
}

function AnalysisMetric({
  icon,
  label,
  value,
  detail,
}: {
  icon: 'analysis' | 'frameworks' | 'shield-check';
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="surface-lift flex items-center gap-3 rounded-xl border border-line-200 bg-surface-0 p-4 shadow-card">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-l bg-leaf-100 text-leaf-700">
        <Icon name={icon} size={19} />
      </span>
      <div className="min-w-0">
        <dt className="text-caption font-semibold text-gray-600">{label}</dt>
        <dd className="mt-0.5 text-title text-forest-900">{value}</dd>
        <dd className="truncate text-caption text-gray-600">{detail}</dd>
      </div>
    </div>
  );
}
