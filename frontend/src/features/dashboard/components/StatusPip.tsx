import { DiamondGlyph, type DiamondVariant } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';
import type { StringKey } from '@/lib/i18n/strings/en';
import type { ComplianceState, DocumentState } from '@/lib/data/contracts';

type PipState = 'complete' | 'inProgress' | 'pending' | 'attention';

const PIP_STYLE: Record<PipState, { glyph: DiamondVariant; className: string }> = {
  complete: { glyph: 'filled', className: 'text-leaf-700' },
  inProgress: { glyph: 'half', className: 'text-leaf-700' },
  pending: { glyph: 'hollow', className: 'text-gray-400' },
  attention: { glyph: 'warning', className: 'text-amber-700' },
};

/** The Qa'ah status language (§12: filled/half/hollow/warning diamond)
 * applied to dashboard rows, so "what state is this in" reads the same way
 * here as it does in the Command Rail and placeholder pages — one status
 * vocabulary for the whole product rather than a new color/icon scheme
 * invented just for the dashboard. */
export function StatusPip({ state, labelKey }: { state: PipState; labelKey: StringKey }) {
  const { t } = useLocale();
  const { glyph, className } = PIP_STYLE[state];
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-meta font-medium', className)}>
      <DiamondGlyph variant={glyph} size={8} />
      {t(labelKey)}
    </span>
  );
}

const DOCUMENT_STATE_PIP: Record<DocumentState, PipState> = {
  processed: 'complete',
  processing: 'inProgress',
  pending: 'pending',
  failed: 'attention',
};

const DOCUMENT_STATE_LABEL_KEY: Record<DocumentState, StringKey> = {
  processed: 'dashboard.status.analyzed',
  processing: 'dashboard.status.processing',
  pending: 'dashboard.status.queued',
  failed: 'dashboard.status.failed',
};

export function DocumentStatusPip({ state }: { state: DocumentState }) {
  return <StatusPip state={DOCUMENT_STATE_PIP[state]} labelKey={DOCUMENT_STATE_LABEL_KEY[state]} />;
}

const COMPLIANCE_STATE_PIP: Record<ComplianceState, PipState> = {
  onTrack: 'complete',
  needsReview: 'attention',
};

const COMPLIANCE_STATE_LABEL_KEY: Record<ComplianceState, StringKey> = {
  onTrack: 'dashboard.status.onTrack',
  needsReview: 'dashboard.status.needsReview',
};

export function ComplianceStatusPip({ state }: { state: ComplianceState }) {
  return (
    <StatusPip state={COMPLIANCE_STATE_PIP[state]} labelKey={COMPLIANCE_STATE_LABEL_KEY[state]} />
  );
}
