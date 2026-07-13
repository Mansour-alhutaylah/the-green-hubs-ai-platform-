import { Link, useParams } from 'react-router';
import { DemoDataBadge, EmptyState, Icon, LoadingSkeleton, SectionCard } from '@/design-system';
import { PageHeader } from '@/shell/PageHeader';
import { MOCK_ANALYSIS_RUNS } from '../mockAnalysisData';
import { AnalysisStatusBadge } from '../components/AnalysisStatusBadge';

export function AnalysisRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const run = MOCK_ANALYSIS_RUNS.find((item) => item.id === runId);

  if (!run) {
    return (
      <div>
        <PageHeader title="Analysis preview" subtitle={runId} action={<DemoDataBadge />} />
        <SectionCard><EmptyState title="This analysis preview is unavailable" description="No AI request was made. Open one of the locally defined sample runs." action={<Link to="/analysis" className="font-semibold text-leaf-700 hover:underline">Back to analysis</Link>} /></SectionCard>
      </div>
    );
  }

  if (run.status === 'PROCESSING') {
    return (
      <div>
        <PageHeader title={run.documentName} subtitle={`Started ${run.startedAt}`} action={<><DemoDataBadge /><AnalysisStatusBadge status={run.status} /></>} />
        <SectionCard title="Analysis in progress" description="Sample processing state · No AI service is running">
          <div className="grid gap-6 lg:grid-cols-2" aria-live="polite">
            <LoadingSkeleton lines={5} label="Analysis summary is processing" />
            <LoadingSkeleton lines={5} label="Analysis findings are processing" />
          </div>
        </SectionCard>
      </div>
    );
  }

  if (run.status === 'FAILED') {
    return (
      <div>
        <PageHeader title={run.documentName} subtitle={`Started ${run.startedAt}`} action={<><DemoDataBadge /><AnalysisStatusBadge status={run.status} /></>} />
        <SectionCard className="border-red-100" aria-live="assertive">
          <EmptyState title="Sample analysis could not be completed" description="The preview demonstrates a recoverable failure state. No provider or backend was contacted." action={<Link to="/analysis" className="font-semibold text-leaf-700 hover:underline">Return to analysis runs</Link>} />
        </SectionCard>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={run.documentName}
        subtitle={`Sample run · Started ${run.startedAt}`}
        action={<><DemoDataBadge label="Preview · Not verified evidence" /><AnalysisStatusBadge status={run.status} /></>}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
        <div className="space-y-5">
          <SectionCard title="Executive summary" description="Sample model output for layout review only.">
            <p className="max-w-3xl text-body leading-7 text-ink-900">{run.summary}</p>
          </SectionCard>

          <SectionCard title="Key findings">
            <ul className="space-y-3">
              {run.findings.map((finding) => (
                <li key={finding} className="flex gap-3 rounded-m bg-tint-100 p-4">
                  <Icon name="check" size={18} className="mt-0.5 shrink-0 text-leaf-700" />
                  <p className="text-body text-ink-900">{finding}</p>
                </li>
              ))}
            </ul>
          </SectionCard>

          <SectionCard title="Recommendations">
            <ol className="space-y-4">
              {run.recommendations.map((recommendation, index) => (
                <li key={recommendation} className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-forest-900 text-micro font-bold text-white">{index + 1}</span>
                  <p className="text-body text-ink-900">{recommendation}</p>
                </li>
              ))}
            </ol>
          </SectionCard>
        </div>

        <div className="space-y-5">
          <SectionCard title="Confidence">
            <div
              role="progressbar"
              aria-label="Sample analysis confidence"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={run.confidence}
            >
              <div className="flex items-end justify-between gap-3"><span className="text-metric text-forest-900">{run.confidence}%</span><span className="text-caption font-semibold text-gray-600">Sample score</span></div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-line-200"><div className="h-full rounded-full bg-leaf-700" style={{ width: `${run.confidence}%` }} /></div>
            </div>
            <p className="mt-3 text-caption text-gray-600">Confidence is illustrative and has not been calibrated against an evaluation dataset.</p>
          </SectionCard>

          <SectionCard title="Source reference">
            <div className="rounded-m border border-amber-100 bg-amber-100 p-4">
              <p className="text-meta font-bold text-amber-700">Sample reference · Not verified evidence</p>
              <p className="mt-2 text-meta text-ink-900">Q3 2025 Sustainability Report.pdf</p>
              <p className="mt-1 text-caption text-gray-600">Pages 18–21 · Preview placeholder</p>
            </div>
            <p className="mt-3 text-caption text-gray-600">Production citations will require source-backed extraction and explicit provenance. This preview does not claim that evidence exists.</p>
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
