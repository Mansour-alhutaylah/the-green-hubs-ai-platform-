import { useEffect } from 'react';
import { useLocale } from '@/lib/i18n/useLocale';
import { useAuth } from '@/features/auth/useAuth';
import { markDashboardVisited } from '@/app/router/dashboardVisited';
import { Avatar, DemoDataBadge, StatusBadge } from '@/design-system';
import { PageHeader } from '@/shell/PageHeader';
import { ROUTES } from '@/app/navigation/routePaths';
import type { StringKey } from '@/lib/i18n/strings/en';
import {
  DASHBOARD_KPIS,
  RECENT_DOCUMENTS,
  RECENT_ANALYSIS,
  RECENT_ACTIVITY,
  COMPLIANCE_FRAMEWORKS,
  PROCESSING_QUEUE,
  type ActivityAction,
} from '../mockDashboardData';
import { DashboardCard } from '../components/DashboardCard';
import { DashboardKpiCard } from '../components/DashboardKpiCard';
import { DocumentStatusPip, ComplianceStatusPip } from '../components/StatusPip';
import { CoachmarksSequence } from '../CoachmarksSequence';

const ACTIVITY_ACTION_KEY: Record<ActivityAction, StringKey> = {
  uploaded: 'dashboard.activity.uploaded',
  approved: 'dashboard.activity.approved',
  viewed: 'dashboard.activity.viewed',
  published: 'dashboard.activity.published',
};

/** The permanent default landing route (§7) — every successful
 * authentication ends up here first. Marking the "visited" flag is what
 * lets subsequent deep links resolve directly for the rest of this browser
 * session (see ProtectedRoute / the landing rule).
 *
 * Enterprise UI Polish Pass: this renders an executive dashboard shell
 * (KPIs, recent documents, AI analysis, activity, compliance, processing
 * queue) built entirely from `mockDashboardData` — static, local, and
 * visibly labeled "Sample data" (§ dashboard.sampleData). No fetching, no
 * calculation, no backend — purely presentational so the landing screen
 * reads as a populated workspace instead of an empty box. */
export function DashboardPage() {
  const { t } = useLocale();
  const { user } = useAuth();

  useEffect(() => {
    markDashboardVisited();
  }, []);

  return (
    <div>
      <PageHeader
        title={t('nav.dashboard')}
        subtitle={user ? `${user.name} · ${user.email}` : undefined}
        action={<DemoDataBadge label={t('dashboard.sampleData')} />}
      />

      <div className="grid grid-cols-1 gap-3 min-[420px]:grid-cols-2 sm:gap-4 xl:grid-cols-4">
        {DASHBOARD_KPIS.map((kpi) => (
          <DashboardKpiCard key={kpi.id} kpi={kpi} />
        ))}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 xl:mt-6 xl:grid-cols-3 xl:gap-6">
        <div className="flex flex-col gap-5 xl:col-span-2 xl:gap-6">
          <DashboardCard title={t('dashboard.section.recentDocuments')} viewAllHref={ROUTES.documents}>
            <ul className="flex flex-col divide-y divide-line-200">
              {RECENT_DOCUMENTS.map((doc) => (
                <li key={doc.id} className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
                  <div className="min-w-0">
                    <p className="truncate text-body font-semibold text-ink-900" data-user-content>
                      {doc.name}
                    </p>
                    <p className="mt-0.5 truncate text-caption text-gray-600" data-user-content>
                      {doc.orgName} · {doc.timestamp}
                    </p>
                  </div>
                  <DocumentStatusPip status={doc.status} />
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard title={t('dashboard.section.recentActivity')}>
            <ul className="flex flex-col divide-y divide-line-200">
              {RECENT_ACTIVITY.map((entry) => (
                <li key={entry.id} className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-1 py-3 first:pt-0 last:pb-0 sm:grid-cols-[auto_minmax(0,1fr)_auto]">
                  <Avatar name={entry.actorName} size={24} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-body text-ink-900" data-user-content>
                      {t(ACTIVITY_ACTION_KEY[entry.action], {
                        actor: entry.actorName,
                        doc: entry.documentName,
                      })}
                    </p>
                  </div>
                  <p className="col-start-2 text-caption text-gray-600 sm:col-start-3">{entry.timestamp}</p>
                </li>
              ))}
            </ul>
          </DashboardCard>
        </div>

        <div className="flex flex-col gap-5 xl:gap-6">
          <DashboardCard title={t('dashboard.section.recentAnalysis')} viewAllHref={ROUTES.analysis}>
            <ul className="flex flex-col divide-y divide-line-200">
              {RECENT_ANALYSIS.map((insight) => (
                <li key={insight.id} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between gap-3">
                    <p
                      className="min-w-0 truncate text-body font-semibold text-ink-900"
                      data-user-content
                    >
                      {insight.documentName}
                    </p>
                    <DocumentStatusPip status={insight.status} />
                  </div>
                  <p className="mt-0.5 text-caption text-gray-600">{insight.detail}</p>
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard title={t('dashboard.section.complianceStatus')} viewAllHref={ROUTES.frameworks}>
            <ul className="flex flex-col divide-y divide-line-200">
              {COMPLIANCE_FRAMEWORKS.map((framework) => (
                <li key={framework.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <p className="min-w-0 truncate text-body font-semibold text-ink-900">
                    {framework.name}
                  </p>
                  <ComplianceStatusPip status={framework.status} />
                </li>
              ))}
            </ul>
          </DashboardCard>

          <DashboardCard title={t('dashboard.section.processingQueue')}>
            <ul className="flex flex-col divide-y divide-line-200">
              {PROCESSING_QUEUE.map((item) => (
                <li key={item.id} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex items-center justify-between gap-3">
                    <p className="min-w-0 truncate text-body text-ink-900" data-user-content>{item.name}</p>
                    <StatusBadge tone="pending">QUEUED</StatusBadge>
                  </div>
                  <p className="mt-1 text-caption text-gray-600">{t('dashboard.queue.eta', { eta: item.eta })}</p>
                </li>
              ))}
            </ul>
          </DashboardCard>
        </div>
      </div>

      <CoachmarksSequence />
    </div>
  );
}
