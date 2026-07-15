import { useEffect } from 'react';
import { Link } from 'react-router';
import { Avatar, Icon, StatusBadge } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { useAuth } from '@/features/auth/useAuth';
import { markDashboardVisited } from '@/app/router/dashboardVisited';
import { ROUTES } from '@/app/navigation/routePaths';
import type { StringKey } from '@/lib/i18n/strings/en';
import { cn } from '@/lib/utils/cn';
import {
  DASHBOARD_KPIS,
  RECENT_DOCUMENTS,
  RECENT_ANALYSIS,
  RECENT_ACTIVITY,
  COMPLIANCE_FRAMEWORKS,
  PROCESSING_QUEUE,
  type ActivityAction,
  type DocumentStatus,
} from '../mockDashboardData';
import { AnalysisActivityChart } from '../components/AnalysisActivityChart';
import { AnalysisSummaryDonut } from '../components/AnalysisSummaryDonut';
import { DashboardCard } from '../components/DashboardCard';
import { DashboardHero } from '../components/DashboardHero';
import { DashboardKpiCard } from '../components/DashboardKpiCard';
import { DocumentStatusPip, ComplianceStatusPip } from '../components/StatusPip';
import { CoachmarksSequence } from '../CoachmarksSequence';

const ACTIVITY_ACTION_KEY: Record<ActivityAction, StringKey> = {
  uploaded: 'dashboard.activity.uploaded',
  approved: 'dashboard.activity.approved',
  viewed: 'dashboard.activity.viewed',
  published: 'dashboard.activity.published',
};

const DOCUMENT_RAIL: Record<DocumentStatus, string> = {
  analyzed: 'before:bg-leaf-500',
  processing: 'before:bg-sky-700',
  queued: 'before:bg-gray-400',
};

/** Static, presentation-only executive workspace. Every figure comes from
 * local mockDashboardData and the hero keeps the demo state visible. */
export function DashboardPage() {
  const { t } = useLocale();
  const { user } = useAuth();

  useEffect(() => {
    markDashboardVisited();
  }, []);

  return (
    <div>
      <DashboardHero user={user} />

      <section className="mt-4 sm:mt-5" aria-labelledby="workspace-overview-heading">
        <h2 id="workspace-overview-heading" className="sr-only">
          {t('dashboard.hero.workspace')}
        </h2>
        <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:gap-4 min-[1440px]:grid-cols-4">
          {DASHBOARD_KPIS.map((kpi) => (
            <DashboardKpiCard key={kpi.id} kpi={kpi} />
          ))}
        </div>
      </section>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:mt-6 xl:grid-cols-3 xl:gap-6">
        <div className="xl:col-span-2">
          <DashboardCard title={t('dashboard.section.analysisActivity')} icon="analysis" eyebrow={t('dashboard.section.insights')}>
            <AnalysisActivityChart />
          </DashboardCard>
        </div>
        <DashboardCard title={t('dashboard.section.analysisSummary')} icon="reports" eyebrow={t('dashboard.section.insights')}>
          <AnalysisSummaryDonut />
        </DashboardCard>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:mt-6 xl:grid-cols-3 xl:gap-6">
        <div className="flex flex-col gap-5 xl:col-span-2 xl:gap-6">
          <DashboardCard
            title={t('dashboard.section.recentDocuments')}
            eyebrow={t('dashboard.section.operations')}
            icon="documents"
            tone="priority"
            viewAllHref={ROUTES.documents}
          >
            <ul className="space-y-2">
              {RECENT_DOCUMENTS.map((document) => (
                <li key={document.id}>
                  <Link
                    to={`/documents/${document.id}`}
                    className={cn(
                      'surface-lift relative grid gap-3 overflow-hidden rounded-l border border-line-200 bg-paper-50 px-4 py-3 before:absolute before:inset-y-0 before:start-0 before:w-1 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center',
                      DOCUMENT_RAIL[document.status],
                    )}
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-m bg-surface-0 text-leaf-700 shadow-card">
                        <Icon name="documents" size={19} />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-body font-bold text-ink-900" data-user-content>
                          {document.name}
                        </span>
                        <span className="mt-0.5 block truncate text-caption text-gray-600" data-user-content>
                          {document.orgName} · {document.timestamp}
                        </span>
                      </span>
                    </span>
                    <span className="justify-self-start sm:justify-self-end">
                      <DocumentStatusPip status={document.status} />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard
            title={t('dashboard.section.recentActivity')}
            icon="audit"
            eyebrow={t('dashboard.section.operations')}
          >
            <ol className="relative ms-3 border-s border-line-200 ps-6">
              {RECENT_ACTIVITY.map((entry, index) => (
                <li key={entry.id} className="relative pb-5 last:pb-0">
                  <span
                    className="absolute -start-7 top-1.5 h-2.5 w-2.5 rounded-full border-2 border-surface-0 bg-leaf-500 shadow-signal"
                    aria-hidden
                  />
                  <div className="flex items-start gap-3">
                    <Avatar name={entry.actorName} size={32} />
                    <div className="min-w-0 flex-1">
                      <p className="text-body text-ink-900" data-user-content>
                        {t(ACTIVITY_ACTION_KEY[entry.action], {
                          actor: entry.actorName,
                          doc: entry.documentName,
                        })}
                      </p>
                      <p className="mt-1 text-caption text-gray-600">
                        {entry.timestamp} · {index === 0 ? 'Latest activity' : 'Workspace history'}
                      </p>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </DashboardCard>
        </div>

        <aside className="flex flex-col gap-5 xl:gap-6" aria-label={t('dashboard.section.insights')}>
          <DashboardCard
            title={t('dashboard.section.recentAnalysis')}
            eyebrow={t('dashboard.section.insights')}
            icon="analysis"
            tone="mint"
            viewAllHref={ROUTES.analysis}
          >
            <ul className="space-y-3">
              {RECENT_ANALYSIS.map((insight, index) => (
                <li key={insight.id}>
                  <Link
                    to={`/analysis/${insight.runId}`}
                    className={cn(
                      'block rounded-l border p-3 transition-colors hover:border-leaf-300 hover:bg-surface-0',
                      index === 0 ? 'border-leaf-300 bg-surface-0 shadow-card' : 'border-transparent',
                    )}
                  >
                    <span className="flex items-start justify-between gap-3">
                      <span className="min-w-0 truncate text-body font-bold text-ink-900" data-user-content>
                        {insight.documentName}
                      </span>
                      <DocumentStatusPip status={insight.status} />
                    </span>
                    <span className="mt-1 block text-caption text-gray-600">{insight.detail}</span>
                    {insight.progress != null && (
                      <>
                        <progress
                          className="sr-only"
                          aria-label={`${insight.documentName} sample processing`}
                          max={100}
                          value={insight.progress}
                        >
                          {insight.progress}%
                        </progress>
                        <span className="mt-2 block h-1 overflow-hidden rounded-full bg-line-200" aria-hidden>
                          <span
                            className="block h-full rounded-full bg-leaf-500"
                            style={{ width: `${insight.progress}%` }}
                          />
                        </span>
                      </>
                    )}
                  </Link>
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard
            title={t('dashboard.section.complianceStatus')}
            icon="frameworks"
            viewAllHref={ROUTES.frameworks}
          >
            <ul className="space-y-2">
              {COMPLIANCE_FRAMEWORKS.map((framework) => (
                <li key={framework.id} className="flex items-center justify-between gap-3 rounded-m bg-tint-100 px-3 py-2.5">
                  <p className="min-w-0 text-meta font-bold text-ink-900">{framework.name}</p>
                  <ComplianceStatusPip status={framework.status} />
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard title={t('dashboard.section.processingQueue')} icon="upload">
            <ol className="space-y-3">
              {PROCESSING_QUEUE.map((item, index) => (
                <li key={item.id} className="flex items-center gap-3">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-m bg-forest-900 text-micro font-bold text-white">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-meta font-bold text-ink-900" data-user-content>
                      {item.name}
                    </span>
                    <span className="block text-caption text-gray-600">
                      {t('dashboard.queue.eta', { eta: item.eta })}
                    </span>
                  </span>
                  <StatusBadge tone="pending">QUEUED</StatusBadge>
                </li>
              ))}
            </ol>
          </DashboardCard>
        </aside>
      </div>

      <CoachmarksSequence />
    </div>
  );
}
