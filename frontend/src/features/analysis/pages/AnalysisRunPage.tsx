import { Link, useParams } from 'react-router';
import {
  DemoDataBadge,
  DiamondGlyph,
  EmptyState,
  Icon,
  LoadingSkeleton,
  SectionCard,
} from '@/design-system';
import { PageHeader } from '@/shell/PageHeader';
import { MOCK_ANALYSIS_RUNS } from '../mockAnalysisData';
import { AnalysisStatusBadge } from '../components/AnalysisStatusBadge';

export function AnalysisRunPage() {
  const { runId } = useParams<{ runId: string }>();
  const run = MOCK_ANALYSIS_RUNS.find((item) => item.id === runId);

  if (!run) {
    return (
      <div>
        <PageHeader
          eyebrow="Analysis intelligence"
          title="Analysis preview"
          subtitle={runId}
          action={<DemoDataBadge />}
        />
        <SectionCard>
          <EmptyState
            title="This analysis preview is unavailable"
            description="No AI request was made. Open one of the locally defined sample runs."
            action={
              <Link to="/analysis" className="font-semibold text-leaf-700 hover:underline">
                Back to analysis
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  if (run.status === 'PROCESSING') {
    return (
      <div>
        <PageHeader
          eyebrow="Analysis intelligence"
          title={run.documentName}
          subtitle={`Started ${run.startedAt}`}
          action={
            <>
              <DemoDataBadge />
              <AnalysisStatusBadge status={run.status} />
            </>
          }
        />
        <section className="mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-6" aria-live="polite">
          <div className="flex items-start gap-4">
            <span className="status-processing flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/8 text-leaf-300">
              <Icon name="analysis" size={24} />
            </span>
            <div>
              <p className="type-label text-leaf-300">Sample processing path</p>
              <h2 className="mt-1 text-title text-white">Analysis in progress</h2>
              <p className="mt-1 text-meta text-white/68">No AI service is running and no provider has been contacted.</p>
            </div>
          </div>
        </section>
        <SectionCard className="rounded-xl border-leaf-300/60 bg-mist-50">
          <div className="grid gap-6 lg:grid-cols-2">
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
        <PageHeader
          eyebrow="Analysis intelligence"
          title={run.documentName}
          subtitle={`Started ${run.startedAt}`}
          action={
            <>
              <DemoDataBadge />
              <AnalysisStatusBadge status={run.status} />
            </>
          }
        />
        <SectionCard className="rounded-xl border-red-100 bg-red-100/30" aria-live="assertive">
          <EmptyState
            title="Sample analysis could not be completed"
            description="The preview demonstrates a recoverable failure state. No provider or backend was contacted."
            action={
              <Link to="/analysis" className="font-semibold text-leaf-700 hover:underline">
                Return to analysis runs
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  const confidence = run.confidence ?? 0;

  return (
    <div>
      <header className="panel-enter relative mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-7">
        <span className="absolute -end-20 -top-28 h-80 w-80 rounded-full border border-leaf-300/20 shadow-[0_0_0_64px_rgb(184_222_195_/_0.035)]" aria-hidden />
        <div className="relative z-10 grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <DemoDataBadge label="Preview · Not verified evidence" />
              <AnalysisStatusBadge status={run.status} />
            </div>
            <p className="type-label mt-5 text-leaf-300">Executive analysis preview</p>
            <h1 className="mt-2 break-words text-display text-white sm:text-hero" data-user-content>
              {run.documentName}
            </h1>
            <p className="mt-2 text-body text-white/68">Sample run · Started {run.startedAt}</p>
            <div className="mt-5 flex flex-wrap gap-2 text-caption font-semibold text-white/72">
              <span className="rounded-full border border-white/15 bg-white/7 px-3 py-1.5">Human review required</span>
              <span className="rounded-full border border-white/15 bg-white/7 px-3 py-1.5">Source provenance pending</span>
            </div>
          </div>

          <div className="flex items-center gap-4 rounded-xl border border-white/12 bg-white/7 p-4 lg:min-w-64">
            <div
              className="relative flex h-24 w-24 shrink-0 items-center justify-center rounded-full p-2"
              style={{
                background: `conic-gradient(var(--color-leaf-500) ${confidence}%, rgb(255 255 255 / 0.13) 0)`,
              }}
              aria-hidden
            >
              <span className="flex h-full w-full items-center justify-center rounded-full bg-forest-900 text-title text-white">
                {confidence}%
              </span>
            </div>
            <div>
              <p className="type-label text-leaf-300">Sample confidence</p>
              <p className="mt-1 text-meta font-bold text-white">Illustrative score</p>
              <p className="mt-1 text-caption text-white/58">Not evaluation-calibrated</p>
            </div>
            <progress
              className="sr-only"
              aria-label="Sample analysis confidence"
              max={100}
              value={confidence}
            >
              {confidence}%
            </progress>
          </div>
        </div>
      </header>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
        <div className="space-y-5">
          <SectionCard
            className="rounded-xl border-leaf-300/70 bg-mist-50"
            title="Executive summary"
            description="Sample model output for layout review only."
          >
            <div className="flex gap-4">
              <span className="mt-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
                <Icon name="analysis" size={18} />
              </span>
              <p className="max-w-3xl text-body leading-7 text-ink-900">{run.summary}</p>
            </div>
          </SectionCard>

          <SectionCard className="rounded-xl" title="Key findings" description="Illustrative observations · Not verified evidence">
            <ul className="grid gap-3 md:grid-cols-2">
              {run.findings.map((finding, index) => (
                <li key={finding} className="rounded-xl border border-line-200 bg-tint-100 p-4">
                  <div className="flex items-center gap-2">
                    <DiamondGlyph variant="hollow" size={10} className="text-leaf-700" />
                    <p className="type-label text-leaf-700">Sample finding {index + 1}</p>
                  </div>
                  <p className="mt-3 text-body text-ink-900">{finding}</p>
                </li>
              ))}
            </ul>
          </SectionCard>

          <SectionCard className="rounded-xl" title="Recommendations" description="Suggested review sequence for demonstration">
            <ol className="space-y-3">
              {run.recommendations.map((recommendation, index) => (
                <li key={recommendation} className="flex gap-4 rounded-l border border-line-200 bg-surface-0 p-4 shadow-card">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-m bg-forest-900 text-caption font-bold text-white">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <div>
                    <p className="type-label text-gray-600">Recommendation</p>
                    <p className="mt-1 text-body text-ink-900">{recommendation}</p>
                  </div>
                </li>
              ))}
            </ol>
          </SectionCard>
        </div>

        <aside className="space-y-5" aria-label="Analysis reference and review boundaries">
          <SectionCard className="rounded-xl border-amber-100" title="Source reference">
            <div className="rounded-l border border-amber-100 bg-amber-100 p-4">
              <div className="flex items-start gap-3">
                <Icon name="documents" size={19} className="mt-0.5 shrink-0 text-amber-700" />
                <div className="min-w-0">
                  <p className="text-meta font-bold text-amber-700">Sample reference · Not verified evidence</p>
                  <p className="mt-2 truncate text-meta text-ink-900">Q3 2025 Sustainability Report.pdf</p>
                  <p className="mt-1 text-caption text-gray-600">Pages 18–21 · Preview placeholder</p>
                </div>
              </div>
            </div>
            <p className="mt-3 text-caption text-gray-600">
              Production citations will require source-backed extraction and explicit provenance. This preview does not claim that evidence exists.
            </p>
          </SectionCard>

          <section className="rounded-xl border border-leaf-300 bg-mist-50 p-5 shadow-card">
            <span className="flex h-10 w-10 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
              <Icon name="shield-check" size={20} />
            </span>
            <h2 className="mt-4 text-panel text-forest-900">Review boundary</h2>
            <p className="mt-1 text-meta text-gray-600">
              Confidence is illustrative and has not been calibrated against an evaluation dataset. Human validation remains required.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
