import { Link } from 'react-router';
import { DemoDataBadge, Icon, SectionCard } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';
import { ROUTES } from '@/app/navigation/routePaths';
import { MOCK_DOCUMENTS } from '../mockDocuments';
import { DocumentStatusBadge } from '../components/DocumentStatusBadge';
import { DocumentCollectionState } from '../components/DocumentCollectionState';

const SUMMARY = [
  { label: 'Total documents', value: '4' },
  { label: 'Processed', value: '1' },
  { label: 'In progress', value: '2' },
  { label: 'Needs attention', value: '1' },
];

export function DocumentsListPage() {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader
        title={t('nav.documents')}
        subtitle="Review source files and their processing state. All records shown here are presentation-only."
        action={
          <>
            <DemoDataBadge label={t('dashboard.sampleData')} />
            <Link
              to={ROUTES.documentUpload}
              className="inline-flex h-10 items-center gap-2 rounded-m bg-forest-900 px-4 text-body font-semibold text-white hover:bg-forest-950"
            >
              <Icon name="upload" size={17} />
              Upload preview
            </Link>
          </>
        }
      />

      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {SUMMARY.map((item) => (
          <div key={item.label} className="rounded-l border border-line-200 bg-surface-0 p-4 shadow-card">
            <dt className="text-caption font-semibold text-gray-600">{item.label}</dt>
            <dd className="mt-1 text-title text-forest-900">{item.value}</dd>
          </div>
        ))}
      </dl>

      <DocumentCollectionState state="ready">
        <SectionCard
          className="mt-5"
          title="Workspace documents"
          description="Sample files demonstrate responsive rows and processing states."
          contentClassName="p-0 sm:p-0"
        >
          <div className="hidden grid-cols-[minmax(0,2fr)_minmax(9rem,1fr)_8rem_10rem] gap-4 border-b border-line-200 bg-tint-100 px-5 py-3 text-caption font-bold text-gray-600 md:grid">
            <span>Document</span>
            <span>Engagement</span>
            <span>Status</span>
            <span>Updated</span>
          </div>

          <ul className="divide-y divide-line-200" aria-label="Sample documents">
            {MOCK_DOCUMENTS.map((document) => (
              <li key={document.id}>
                <Link
                  to={`/documents/${document.id}`}
                  className="group grid gap-3 px-4 py-4 transition-colors hover:bg-tint-100 sm:px-5 md:grid-cols-[minmax(0,2fr)_minmax(9rem,1fr)_8rem_10rem] md:items-center md:gap-4"
                >
                  <span className="flex min-w-0 items-start gap-3">
                    <span className="mt-0.5 rounded-m bg-leaf-100 p-2 text-leaf-700" aria-hidden>
                      <Icon name="documents" size={18} />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-body font-bold text-ink-900 group-hover:text-leaf-700" data-user-content>
                        {document.name}
                      </span>
                      <span className="mt-0.5 block text-caption text-gray-600">
                        {document.type} · {document.size} · {document.owner}
                      </span>
                    </span>
                  </span>
                  <span className="truncate text-meta text-gray-600" data-user-content>
                    {document.engagement}
                  </span>
                  <span><DocumentStatusBadge status={document.status} /></span>
                  <time className="text-caption text-gray-600">{document.updatedAt}</time>
                </Link>
              </li>
            ))}
          </ul>
        </SectionCard>
      </DocumentCollectionState>
    </div>
  );
}
