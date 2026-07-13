import { Link, useParams } from 'react-router';
import { DemoDataBadge, EmptyState, SectionCard } from '@/design-system';
import { PageHeader } from '@/shell/PageHeader';
import { MOCK_DOCUMENTS, type DocumentProcessingStatus } from '../mockDocuments';
import { DocumentStatusBadge } from '../components/DocumentStatusBadge';

const TIMELINE_STEPS: Array<{ status: DocumentProcessingStatus; label: string; description: string }> = [
  { status: 'PENDING', label: 'Received', description: 'File registered in the preview queue' },
  { status: 'PROCESSING', label: 'Processing', description: 'Text extraction and quality checks' },
  { status: 'PROCESSED', label: 'Ready for review', description: 'Processing completed successfully' },
];

const STEP_ORDER: Record<DocumentProcessingStatus, number> = {
  PENDING: 0,
  PROCESSING: 1,
  PROCESSED: 2,
  FAILED: 1,
};

export function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const document = MOCK_DOCUMENTS.find((item) => item.id === id);

  if (!document) {
    return (
      <div>
        <PageHeader title="Document preview" subtitle={id} action={<DemoDataBadge />} />
        <SectionCard>
          <EmptyState
            title="This sample document is unavailable"
            description="Only locally defined preview records can be opened in this frontend sprint."
            action={<Link className="font-semibold text-leaf-700 hover:underline" to="/documents">Back to documents</Link>}
          />
        </SectionCard>
      </div>
    );
  }

  const currentStep = STEP_ORDER[document.status];

  return (
    <div>
      <PageHeader
        title={document.name}
        subtitle={document.engagement}
        action={<><DemoDataBadge /><DocumentStatusBadge status={document.status} /></>}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
        <SectionCard title="Processing timeline" description="Preview of the document lifecycle. No processing is running.">
          <ol className="space-y-0">
            {TIMELINE_STEPS.map((step, index) => {
              const complete = index < currentStep || document.status === 'PROCESSED';
              const active = index === currentStep && document.status !== 'FAILED';
              const failed = document.status === 'FAILED' && index === currentStep;
              return (
                <li key={step.status} className="relative flex gap-4 pb-7 last:pb-0">
                  {index < TIMELINE_STEPS.length - 1 && (
                    <span className="absolute start-[11px] top-6 h-[calc(100%-8px)] w-px bg-line-200" aria-hidden />
                  )}
                  <span
                    className={`relative z-10 mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-micro font-bold ${
                      failed
                        ? 'border-red-700 bg-red-100 text-red-700'
                        : complete
                          ? 'border-leaf-700 bg-leaf-700 text-white'
                          : active
                            ? 'border-leaf-700 bg-leaf-100 text-leaf-700'
                            : 'border-line-300 bg-surface-0 text-gray-600'
                    }`}
                    aria-hidden
                  >
                    {failed ? '!' : complete ? '✓' : index + 1}
                  </span>
                  <div>
                    <p className="text-body font-bold text-ink-900">{failed ? 'Processing failed' : step.label}</p>
                    <p className="mt-0.5 text-meta text-gray-600">
                      {failed ? 'The sample parser could not complete this file.' : step.description}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </SectionCard>

        <SectionCard title="Document details">
          <dl className="divide-y divide-line-200">
            {[
              ['File type', document.type],
              ['File size', document.size],
              ['Uploaded by', document.owner],
              ['Uploaded', document.uploadedAt],
              ['Last updated', document.updatedAt],
            ].map(([label, value]) => (
              <div key={label} className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0">
                <dt className="text-meta text-gray-600">{label}</dt>
                <dd className="text-end text-meta font-semibold text-ink-900" data-user-content>{value}</dd>
              </div>
            ))}
          </dl>
        </SectionCard>
      </div>
    </div>
  );
}
