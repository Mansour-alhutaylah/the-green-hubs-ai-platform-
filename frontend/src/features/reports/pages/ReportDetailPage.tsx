import { useState } from 'react';
import { Link, useParams } from 'react-router';
import {
  Button,
  DemoDataBadge,
  Icon,
  LoadingSkeleton,
  SectionCard,
  StateBlock,
} from '@/design-system';
import { ROUTES } from '@/app/navigation/routePaths';
import { DetailList } from '@/features/workspace/components/DetailList';
import { useReportDetail } from '@/lib/data/hooks/useExecutiveData';
import type { ReportFramework } from '@/lib/data/contracts';
import { isPreviewMode } from '@/lib/data/source';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import { formatDateTime } from '@/lib/utils/formatDate';
import { PageHeader } from '@/shell/PageHeader';
import { ReadinessMeter, ReportStatusBadge } from '../components/ReportStatusBadge';

/**
 * A single report, reached as a registered detail route rather than a
 * modal, so it is deep-linkable and the browser's back button behaves.
 *
 * Preview only. In Live the source resolves to `unavailable` and this page
 * says so: no reporting endpoint exists, so there is no report to fetch
 * and none to invent. An unknown id in Preview resolves to `not-found`,
 * which is distinct from both.
 *
 * The section list is the substance. It shows how many evidence documents
 * are attached to each part of the report and which parts are still short,
 * which is the question someone opens a report to answer. Nothing here
 * claims the report has been filed or accepted anywhere.
 */

const FRAMEWORK_LABEL_KEY: Record<ReportFramework, StringKey> = {
  gri: 'reports.framework.gri',
  csrd: 'reports.framework.csrd',
  issb: 'reports.framework.issb',
  internal: 'reports.framework.internal',
};

export function ReportDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useLocale();
  const preview = isPreviewMode();
  const state = useReportDetail(id);
  const [notice, setNotice] = useState<string | null>(null);

  const report = state.status === 'ready' ? state.data : null;

  return (
    <div>
      <PageHeader
        eyebrow={t('reports.detail.eyebrow')}
        title={report?.name ?? t('nav.reports')}
        subtitle={report ? undefined : t('reports.detail.subtitle')}
        action={preview ? <DemoDataBadge label={t('dashboard.sampleData')} /> : undefined}
      />

      <p className="mb-4">
        <Link
          to={ROUTES.reports}
          className="inline-flex items-center gap-1.5 text-meta font-semibold text-leaf-700 underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
        >
          <Icon name="reports" size={15} />
          {t('reports.detail.backToList')}
        </Link>
      </p>

      {report ? (
        <div className="flex flex-col gap-4 sm:gap-5">
          <SectionCard
            title={t('reports.detail.profile.title')}
            description={t('reports.detail.profile.description')}
          >
            <DetailList
              items={[
                {
                  id: 'framework',
                  label: t('reports.table.column.framework'),
                  value: t(FRAMEWORK_LABEL_KEY[report.framework]),
                },
                {
                  id: 'status',
                  label: t('reports.table.column.status'),
                  value: <ReportStatusBadge status={report.status} />,
                },
                {
                  id: 'readiness',
                  label: t('reports.table.column.readiness'),
                  value: <ReadinessMeter percent={report.readinessPercent} />,
                },
                {
                  id: 'owner',
                  label: t('reports.table.column.owner'),
                  value: <span data-user-content>{report.owner}</span>,
                },
                {
                  id: 'period',
                  label: t('reports.detail.field.period'),
                  value: report.period,
                },
                {
                  id: 'updated',
                  label: t('reports.table.column.updated'),
                  value: (
                    <time dir="ltr" dateTime={report.updatedAt}>
                      {formatDateTime(report.updatedAt)}
                    </time>
                  ),
                },
              ]}
            />
          </SectionCard>

          <SectionCard
            title={t('reports.detail.sections.title')}
            description={t('reports.detail.sections.description')}
            contentClassName="p-0 sm:p-0"
          >
            <ul className="divide-y divide-line-200 px-4 sm:px-5">
              {report.sections.map((section) => (
                <li
                  key={section.id}
                  className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3"
                >
                  <span className="min-w-0 text-body font-semibold text-forest-900">
                    {section.title}
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="text-caption text-gray-600">
                      {t('reports.detail.sections.evidence', { count: section.evidenceCount })}
                    </span>
                    <span
                      className={
                        section.complete
                          ? 'rounded-full border border-leaf-300 bg-leaf-100 px-2.5 py-0.5 text-caption font-bold text-leaf-700'
                          : 'rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-caption font-bold text-amber-700'
                      }
                    >
                      {section.complete
                        ? t('reports.detail.sections.complete')
                        : t('reports.detail.sections.incomplete')}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </SectionCard>

          <SectionCard
            title={t('reports.detail.actions.title')}
            description={t('reports.detail.actions.description')}
          >
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setNotice(t('reports.generate.notice'))}
              >
                {t('reports.generate.action')}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setNotice(t('reports.export.notice'))}
              >
                {t('reports.export.action')}
              </Button>
            </div>
            {notice && (
              <output className="mt-4 block rounded-m border border-dashed border-line-300 bg-tint-100 px-4 py-3 text-meta text-gray-600">
                {notice}
              </output>
            )}
          </SectionCard>
        </div>
      ) : (
        <SectionCard>
          <StateBlock
            status={state.status === 'ready' ? 'error' : state.status}
            loadingLabel={t('workspace.state.loading')}
            loadingSkeleton={<LoadingSkeleton lines={5} label={t('workspace.state.loading')} />}
            title={
              state.status === 'unavailable'
                ? t('reports.unavailable.title')
                : state.status === 'not-found'
                  ? t('workspace.state.notFound.title')
                  : state.status === 'forbidden'
                    ? t('workspace.state.forbidden.title')
                    : state.status === 'loading'
                      ? t('workspace.state.loading')
                      : t('workspace.state.error.title')
            }
            description={
              state.status === 'unavailable'
                ? t('reports.unavailable.description')
                : state.status === 'not-found'
                  ? t('workspace.state.notFound.description')
                  : state.status === 'forbidden'
                    ? t('workspace.state.forbidden.description')
                    : state.status === 'error'
                      ? t('workspace.state.error.description')
                      : undefined
            }
          />
        </SectionCard>
      )}
    </div>
  );
}
