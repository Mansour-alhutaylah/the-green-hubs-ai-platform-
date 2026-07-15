import { Link, useParams } from 'react-router';
import { Button, DemoDataBadge, EmptyState, Icon, SectionCard } from '@/design-system';
import { PageHeader } from '@/shell/PageHeader';
import { cn } from '@/lib/utils/cn';
import { MOCK_DOCUMENTS, type DocumentProcessingStatus } from '../mockDocuments';
import { DocumentStatusBadge } from '../components/DocumentStatusBadge';

const TIMELINE_STEPS: Array<{
  status: DocumentProcessingStatus;
  label: string;
  description: string;
}> = [
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
        <PageHeader
          eyebrow="Document intelligence"
          title="Document preview"
          subtitle={id}
          action={<DemoDataBadge />}
        />
        <SectionCard>
          <EmptyState
            title="This sample document is unavailable"
            description="Only locally defined preview records can be opened in this frontend sprint."
            action={
              <Link className="font-semibold text-leaf-700 hover:underline" to="/documents">
                Back to documents
              </Link>
            }
          />
        </SectionCard>
      </div>
    );
  }

  const currentStep = STEP_ORDER[document.status];

  return (
    <div>
      <PageHeader
        eyebrow="Document intelligence"
        title={document.name}
        subtitle={document.engagement}
        action={
          <>
            <DemoDataBadge />
            <DocumentStatusBadge status={document.status} />
          </>
        }
      />

      <section className="relative mb-5 overflow-hidden rounded-xl border border-white/10 bg-forest-900 p-5 text-white shadow-brand sm:p-6">
        <span className="absolute -end-16 -top-20 h-56 w-56 rounded-full border border-leaf-300/20 shadow-[0_0_0_48px_rgb(184_222_195_/_0.035)]" aria-hidden />
        <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex min-w-0 items-start gap-4">
            <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border border-white/15 bg-white/8 text-leaf-300 shadow-raise">
              <Icon name="documents" size={26} />
            </span>
            <div className="min-w-0">
              <p className="type-label text-leaf-300">Source document</p>
              <p className="mt-1 truncate text-title text-white" data-user-content>
                {document.name}
              </p>
              <p className="mt-1 text-caption text-white/62">
                {document.type} · {document.size} · Local preview record
              </p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:min-w-[28rem]">
            <IdentityMetric label="Owner" value={document.owner} />
            <IdentityMetric label="Uploaded" value={document.uploadedAt} />
            <IdentityMetric label="Current state" value={document.status} />
          </dl>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
        <SectionCard
          className="rounded-xl border-leaf-300/60"
          title="Processing journey"
          description="Preview of the document lifecycle. No processing is running."
          action={<DocumentStatusBadge status={document.status} />}
        >
          <ol className="space-y-0">
            {TIMELINE_STEPS.map((step, index) => {
              const complete = index < currentStep || document.status === 'PROCESSED';
              const active = index === currentStep && document.status !== 'FAILED';
              const failed = document.status === 'FAILED' && index === currentStep;
              const isCurrent = active || failed;

              return (
                <li
                  key={step.status}
                  className="relative flex gap-4 pb-8 last:pb-0"
                  aria-current={isCurrent ? 'step' : undefined}
                >
                  {index < TIMELINE_STEPS.length - 1 && (
                    <span
                      className={cn(
                        'absolute start-[15px] top-8 h-[calc(100%-8px)] w-px',
                        complete ? 'bg-leaf-500' : 'bg-line-200',
                      )}
                      aria-hidden
                    />
                  )}
                  <span
                    className={cn(
                      'relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-micro font-bold shadow-card',
                      failed && 'border-red-700 bg-red-100 text-red-700',
                      complete && !failed && 'border-leaf-700 bg-leaf-700 text-white',
                      active && !complete && 'border-leaf-700 bg-leaf-100 text-leaf-700',
                      !failed && !complete && !active && 'border-line-300 bg-surface-0 text-gray-600',
                    )}
                    aria-hidden
                  >
                    {failed ? (
                      <Icon name="circle-alert" size={15} />
                    ) : complete ? (
                      <Icon name="check" size={15} />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <div className="min-w-0 rounded-l border border-line-200 bg-tint-100 px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-body font-bold text-ink-900">
                        {failed ? 'Processing failed' : step.label}
                      </p>
                      {isCurrent && (
                        <span className="type-label rounded-full bg-surface-0 px-2 py-0.5 text-leaf-700">
                          Current sample state
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-meta text-gray-600">
                      {failed
                        ? 'The sample parser could not complete this file.'
                        : step.description}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </SectionCard>

        <div className="space-y-5">
          <SectionCard className="rounded-xl" title="Source metadata">
            <dl className="divide-y divide-line-200">
              {[
                ['File type', document.type],
                ['File size', document.size],
                ['Uploaded by', document.owner],
                ['Uploaded', document.uploadedAt],
                ['Last updated', document.updatedAt],
              ].map(([label, value]) => (
                <div
                  key={label}
                  className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0"
                >
                  <dt className="text-meta text-gray-600">{label}</dt>
                  <dd className="text-end text-meta font-semibold text-ink-900" data-user-content>
                    {value}
                  </dd>
                </div>
              ))}
            </dl>
          </SectionCard>

          <section className="rounded-xl border border-leaf-300 bg-mist-50 p-5 shadow-card">
            <span className="flex h-10 w-10 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
              <Icon name="analysis" size={20} />
            </span>
            <h2 className="mt-4 text-panel text-forest-900">Intelligence handoff</h2>
            <p className="mt-1 text-meta text-gray-600">
              No generated intelligence exists for this preview. A connected workflow would require explicit review and provenance.
            </p>
            <Button disabled size="md" className="mt-4 w-full">
              Analysis unavailable in preview
            </Button>
          </section>
        </div>
      </div>
    </div>
  );
}

function IdentityMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 border-s border-white/12 ps-3 first:border-s-0 first:ps-0">
      <dt className="text-caption text-white/58">{label}</dt>
      <dd className="mt-0.5 truncate text-meta font-bold text-white" data-user-content>
        {value}
      </dd>
    </div>
  );
}
