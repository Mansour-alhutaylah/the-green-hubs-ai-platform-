import { DemoDataBadge, SectionCard } from '@/design-system';
import type { ExecutiveSummary } from '@/lib/data/contracts';
import { useLocale } from '@/lib/i18n/useLocale';
import { ActionCentre } from './ActionCentre';
import { EvidenceKpiRow, type EvidenceKpi } from './EvidenceKpiRow';
import { EvidencePipeline } from './EvidencePipeline';
import { EvidenceThroughputChart } from './EvidenceThroughputChart';
import { FrameworkCoverageList } from './FrameworkCoverageList';

/**
 * The Preview command centre, in the order an executive reads it:
 *
 *   four KPIs  ->  throughput + what to do next  ->  pipeline + framework
 *
 * The two-column rows are the substance of the redesign. Throughput
 * answers "what changed" and the Action Centre answers "what needs me",
 * and those are the two questions that belong side by side in the first
 * screenful after the KPIs. Pipeline and framework coverage answer "where
 * is the work" and "what is it for", which are follow-ups.
 *
 * Sample-data labelling sits on the two panels carrying invented figures
 * rather than on all four. The global Preview ribbon already establishes
 * the mode; repeating it on every card is how a reviewer learns to stop
 * seeing it.
 */
export function DashboardExecutiveView({
  summary,
  isPartial,
}: {
  summary: ExecutiveSummary;
  isPartial: boolean;
}) {
  const { t } = useLocale();

  const kpis: readonly EvidenceKpi[] = [
    {
      id: 'readiness',
      label: t('dashboard.kpi.evidenceReadiness'),
      value: summary.evidenceReadinessPercent,
      unit: 'percent',
      definition: t('dashboard.kpi.evidenceReadiness.definition'),
      context: t('dashboard.kpi.evidenceReadiness.context', {
        ready: summary.pipeline.find((stage) => stage.stage === 'reportReady')?.count ?? 0,
        total: summary.sourceDocuments,
      }),
      icon: 'audit',
      tone: 'neutral',
    },
    {
      id: 'documents',
      label: t('dashboard.kpi.sourceDocuments'),
      value: summary.sourceDocuments,
      unit: 'count',
      definition: t('dashboard.kpi.sourceDocuments.definition'),
      context: t('dashboard.kpi.sourceDocuments.context', { period: summary.reportingPeriod }),
      icon: 'documents',
      tone: 'neutral',
    },
    {
      id: 'awaiting',
      label: t('dashboard.kpi.awaitingReview'),
      value: summary.awaitingReview,
      unit: 'count',
      definition: t('dashboard.kpi.awaitingReview.definition'),
      context: t('dashboard.kpi.awaitingReview.context'),
      icon: 'eye',
      tone: summary.awaitingReview > 0 ? 'warning' : 'neutral',
    },
    {
      id: 'processing',
      label: t('dashboard.kpi.processingHealth'),
      value: summary.processingHealthPercent,
      unit: 'percent',
      definition: t('dashboard.kpi.processingHealth.definition'),
      context: t('dashboard.kpi.processingHealth.context', {
        failures: summary.processingFailures,
      }),
      icon: 'refresh',
      tone: summary.processingFailures > 0 ? 'warning' : 'positive',
    },
  ];

  return (
    <div className="mt-4 flex flex-col gap-4 sm:mt-5 sm:gap-5">
      <EvidenceKpiRow items={kpis} />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.65fr)_minmax(0,1fr)] xl:gap-5">
        <SectionCard
          title={t('dashboard.throughput.title')}
          description={t('dashboard.throughput.description')}
          action={<DemoDataBadge label={t('dashboard.sampleData')} />}
        >
          <EvidenceThroughputChart
            points={summary.throughput}
            period={summary.reportingPeriod}
          />
        </SectionCard>

        <SectionCard
          title={t('dashboard.action.title')}
          description={t('dashboard.action.description')}
          contentClassName="p-0 sm:p-0"
        >
          <div className="px-4 pb-2 sm:px-5">
            <ActionCentre actions={summary.actions} />
          </div>
        </SectionCard>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2 xl:gap-5">
        <SectionCard
          title={t('dashboard.pipeline.title')}
          description={t('dashboard.pipeline.description')}
        >
          <EvidencePipeline stages={summary.pipeline} />
        </SectionCard>

        <SectionCard
          title={t('dashboard.framework.title')}
          description={t('dashboard.framework.description')}
          action={<DemoDataBadge label={t('dashboard.sampleData')} />}
        >
          <FrameworkCoverageList frameworks={summary.frameworks} />
        </SectionCard>
      </div>

      {isPartial && (
        <p className="text-meta font-semibold text-gray-600">{t('workspace.state.partial')}</p>
      )}
    </div>
  );
}
