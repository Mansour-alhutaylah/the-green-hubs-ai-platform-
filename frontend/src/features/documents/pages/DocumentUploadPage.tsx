import { useState, type ChangeEvent } from 'react';
import { Button, DemoDataBadge, Icon, SectionCard, StatusBadge } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';

const MAX_FILE_SIZE = 25 * 1024 * 1024;

/** Frontend validation preview only. It never sends or persists the selected file. */
export function DocumentUploadPage() {
  const { t } = useLocale();
  const [selectedFile, setSelectedFile] = useState<File>();
  const [error, setError] = useState<string>();

  function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setSelectedFile(undefined);
    setError(undefined);
    if (!file) return;
    if (file.type !== 'application/pdf' || !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Choose a PDF file. Other formats are not accepted in this preview.');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError('This file is larger than the 25 MB preview limit.');
      return;
    }
    setSelectedFile(file);
  }

  return (
    <div>
      <PageHeader
        title={t('nav.upload')}
        subtitle="Validate the upload experience without sending a document to any service."
        action={<DemoDataBadge label="Preview · No persistence" />}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
        <SectionCard title="Choose a source document" description="PDF only · Maximum 25 MB">
          <label className="group flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-l border-2 border-dashed border-line-300 bg-tint-100 px-6 py-10 text-center transition-colors hover:border-leaf-700 hover:bg-leaf-100 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-leaf-500">
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              onChange={handleFile}
              aria-describedby="upload-support upload-error"
            />
            <span className="rounded-full bg-surface-0 p-4 text-leaf-700 shadow-raise" aria-hidden>
              <Icon name="upload" size={24} />
            </span>
            <span className="mt-5 text-panel text-forest-900">Select a PDF document</span>
            <span id="upload-support" className="mt-1 max-w-md text-meta text-gray-600">
              Drag-and-drop styling is shown for preview; use this control to browse with mouse or keyboard.
            </span>
          </label>

          <div id="upload-error" aria-live="polite">
            {error && (
              <div className="mt-4 flex items-start gap-3 rounded-m border border-red-100 bg-red-100 p-4 text-red-700">
                <Icon name="circle-alert" size={18} className="mt-0.5 shrink-0" />
                <p className="text-meta font-semibold">{error}</p>
              </div>
            )}
            {selectedFile && (
              <div className="mt-4 flex flex-col gap-3 rounded-m border border-leaf-300 bg-leaf-100 p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-body font-bold text-ink-900" data-user-content>{selectedFile.name}</p>
                  <p className="mt-0.5 text-caption text-gray-600">{(selectedFile.size / 1024 / 1024).toFixed(1)} MB · Local selection only</p>
                </div>
                <StatusBadge tone="success">VALIDATED</StatusBadge>
              </div>
            )}
          </div>

          <Button disabled className="mt-5 w-full sm:w-auto" aria-describedby="upload-disabled-note">
            Upload unavailable in preview
          </Button>
          <p id="upload-disabled-note" className="mt-2 text-caption text-gray-600">
            No backend request is made and this selection will not be saved.
          </p>
        </SectionCard>

        <SectionCard title="What happens next">
          <ol className="space-y-5">
            {[
              ['1', 'Validate', 'File type and size are checked locally.'],
              ['2', 'Process', 'A future connected service will extract document text.'],
              ['3', 'Review', 'Results will remain subject to human review.'],
            ].map(([number, title, body]) => (
              <li key={number} className="flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-forest-900 text-caption font-bold text-white">{number}</span>
                <div><p className="text-meta font-bold text-ink-900">{title}</p><p className="mt-0.5 text-caption text-gray-600">{body}</p></div>
              </li>
            ))}
          </ol>
          <div className="mt-6 rounded-m border border-amber-100 bg-amber-100 p-4">
            <p className="text-meta font-bold text-amber-700">Preview safeguard</p>
            <p className="mt-1 text-caption text-amber-700">Do not select confidential material. This screen demonstrates interface states only.</p>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
