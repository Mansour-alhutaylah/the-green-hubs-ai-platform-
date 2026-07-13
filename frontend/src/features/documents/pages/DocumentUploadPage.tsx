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
        eyebrow="Document intake"
        title={t('nav.upload')}
        subtitle="Validate the source-document experience locally without sending a file to any service."
        action={<DemoDataBadge label="Preview · No persistence" />}
      />

      <div className="grid gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
        <SectionCard
          className="rounded-xl border-leaf-300/70"
          title="Choose a source document"
          description="Local interface validation only"
          action={
            <div className="flex gap-2">
              <span className="rounded-full border border-leaf-300 bg-leaf-100 px-2.5 py-1 text-caption font-bold text-leaf-700">
                PDF only
              </span>
              <span className="rounded-full border border-line-200 bg-tint-100 px-2.5 py-1 text-caption font-bold text-gray-600">
                25 MB max
              </span>
            </div>
          }
        >
          <label className="group relative flex min-h-72 cursor-pointer flex-col items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-leaf-500 bg-forest-900 px-6 py-10 text-center text-white shadow-brand transition-colors hover:border-leaf-300 hover:bg-forest-800 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-forest-900">
            <input
              type="file"
              accept="application/pdf,.pdf"
              className="sr-only"
              onChange={handleFile}
              aria-describedby="upload-support upload-error"
            />
            <span className="absolute -end-14 -top-20 h-52 w-52 rounded-full border border-leaf-300/20 shadow-[0_0_0_44px_rgb(184_222_195_/_0.04)]" aria-hidden />
            <span className="absolute -bottom-24 -start-10 h-52 w-52 rounded-full border border-leaf-300/15" aria-hidden />
            <span className="relative flex h-16 w-16 items-center justify-center rounded-xl border border-white/15 bg-white/10 text-leaf-300 shadow-float transition-transform duration-[var(--motion-base)] group-hover:-translate-y-1" aria-hidden>
              <Icon name="upload" size={28} />
            </span>
            <span className="relative mt-5 text-title text-white">Select a PDF document</span>
            <span id="upload-support" className="relative mt-2 max-w-md text-meta text-white/68">
              Browse with mouse, touch, or keyboard. Drag-and-drop is not enabled in this preview.
            </span>
            <span className="relative mt-5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/7 px-3 py-1.5 text-caption font-semibold text-white/78">
              <Icon name="shield-check" size={15} />
              Nothing is transmitted or stored
            </span>
          </label>

          <div id="upload-error" aria-live="polite">
            {error && (
              <div className="mt-4 flex items-start gap-3 rounded-l border border-red-100 bg-red-100 p-4 text-red-700">
                <Icon name="circle-alert" size={18} className="mt-0.5 shrink-0" />
                <p className="text-meta font-semibold">{error}</p>
              </div>
            )}
            {selectedFile && (
              <div className="mt-4 flex flex-col gap-4 rounded-xl border border-leaf-300 bg-mist-50 p-4 shadow-card sm:flex-row sm:items-center sm:justify-between">
                <div className="flex min-w-0 items-center gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
                    <Icon name="documents" size={20} />
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-body font-bold text-ink-900" data-user-content>
                      {selectedFile.name}
                    </p>
                    <p className="mt-0.5 text-caption text-gray-600">
                      {(selectedFile.size / 1024 / 1024).toFixed(1)} MB · Local selection only
                    </p>
                  </div>
                </div>
                <StatusBadge tone="success">VALIDATED</StatusBadge>
              </div>
            )}
          </div>

          <div className="mt-5 rounded-l border border-line-200 bg-tint-100 p-4">
            <Button disabled className="w-full sm:w-auto" aria-describedby="upload-disabled-note">
              Upload unavailable in preview
            </Button>
            <p id="upload-disabled-note" className="mt-2 text-caption text-gray-600">
              No backend request is made and this selection will not be saved.
            </p>
          </div>
        </SectionCard>

        <div className="space-y-5">
          <SectionCard className="rounded-xl" title="Preview workflow" description="How a connected production flow would be structured">
            <ol className="relative ms-3 border-s border-line-200 ps-6">
              {[
                ['1', 'Validate locally', 'File type and size are checked in this browser.'],
                ['2', 'Process with consent', 'A future connected service would require an explicit action.'],
                ['3', 'Review with provenance', 'Any future output would remain subject to human review.'],
              ].map(([number, title, body]) => (
                <li key={number} className="relative pb-6 last:pb-0">
                  <span className="absolute -start-10 flex h-8 w-8 items-center justify-center rounded-full border-4 border-surface-0 bg-forest-900 text-micro font-bold text-white">
                    {number}
                  </span>
                  <p className="text-meta font-bold text-ink-900">{title}</p>
                  <p className="mt-1 text-caption text-gray-600">{body}</p>
                </li>
              ))}
            </ol>
          </SectionCard>

          <section className="rounded-xl border border-leaf-300 bg-mist-50 p-5 shadow-card">
            <span className="flex h-10 w-10 items-center justify-center rounded-l bg-forest-900 text-leaf-300">
              <Icon name="shield-check" size={20} />
            </span>
            <h2 className="mt-4 text-panel text-forest-900">Preview safeguard</h2>
            <p className="mt-1 text-meta text-gray-600">
              Do not select confidential material. The chosen file remains a temporary browser selection and is neither transmitted nor persisted.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
