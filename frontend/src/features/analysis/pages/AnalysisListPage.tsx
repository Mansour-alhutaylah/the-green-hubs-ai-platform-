import { Link } from 'react-router';
import { DemoDataBadge, EmptyState, Icon, LoadingSkeleton, SectionCard } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';
import { MOCK_ANALYSIS_RUNS } from '../mockAnalysisData';
import { AnalysisStatusBadge } from '../components/AnalysisStatusBadge';

export function AnalysisListPage() {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader
        title={t('nav.analysis')}
        subtitle="Preview analysis runs, review states, and source handling without invoking an AI service."
        action={<DemoDataBadge label="Sample data · Analysis preview" />}
      />

      <SectionCard
        title="Recent analysis runs"
        description="Static examples demonstrate complete, processing, and failed states."
        contentClassName="p-0 sm:p-0"
      >
        <ul className="divide-y divide-line-200" aria-label="Sample analysis runs">
          {MOCK_ANALYSIS_RUNS.map((run) => (
            <li key={run.id}>
              <Link
                to={`/analysis/${run.id}`}
                className="group flex flex-col gap-3 px-4 py-4 hover:bg-tint-100 sm:flex-row sm:items-center sm:justify-between sm:px-5"
              >
                <span className="flex min-w-0 items-start gap-3">
                  <span className="mt-0.5 rounded-m bg-leaf-100 p-2 text-leaf-700" aria-hidden><Icon name="analysis" size={18} /></span>
                  <span className="min-w-0">
                    <span className="block truncate text-body font-bold text-ink-900 group-hover:text-leaf-700" data-user-content>{run.documentName}</span>
                    <span className="mt-0.5 block text-caption text-gray-600">Started {run.startedAt}</span>
                  </span>
                </span>
                <span className="flex items-center gap-3 self-start sm:self-auto">
                  {run.confidence != null && <span className="text-caption font-semibold text-gray-600">{run.confidence}% confidence</span>}
                  <AnalysisStatusBadge status={run.status} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </SectionCard>

      <div className="mt-5 grid gap-5 lg:grid-cols-3" aria-label="Analysis state examples">
        <SectionCard title="Before processing"><EmptyState title="No analysis yet" description="A connected workflow will show eligible documents here." className="py-5" /></SectionCard>
        <SectionCard title="Processing"><LoadingSkeleton lines={4} label="Sample analysis is processing" /></SectionCard>
        <SectionCard title="Unavailable"><EmptyState title="Analysis not available" description="Unsupported files remain visible with a clear reason." className="py-5" /></SectionCard>
      </div>
    </div>
  );
}
