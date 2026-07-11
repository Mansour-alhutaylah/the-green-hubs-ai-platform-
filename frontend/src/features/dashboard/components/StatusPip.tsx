import { DiamondGlyph, type DiamondVariant } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { cn } from '@/lib/utils/cn';
import type { StringKey } from '@/lib/i18n/strings/en';
import type { ComplianceState, DocumentStatus } from '../mockDashboardData';

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

const DOCUMENT_STATUS_STATE: Record<DocumentStatus, PipState> = {
  analyzed: 'complete',
  processing: 'inProgress',
  queued: 'pending',
};

const DOCUMENT_STATUS_LABEL_KEY: Record<DocumentStatus, StringKey> = {
  analyzed: 'dashboard.status.analyzed',
  processing: 'dashboard.status.processing',
  queued: 'dashboard.status.queued',
};

export function DocumentStatusPip({ status }: { status: DocumentStatus }) {
  return <StatusPip state={DOCUMENT_STATUS_STATE[status]} labelKey={DOCUMENT_STATUS_LABEL_KEY[status]} />;
}

const COMPLIANCE_STATE_PIP: Record<ComplianceState, PipState> = {
  onTrack: 'complete',
  needsReview: 'attention',
};

const COMPLIANCE_STATE_LABEL_KEY: Record<ComplianceState, StringKey> = {
  onTrack: 'dashboard.status.onTrack',
  needsReview: 'dashboard.status.needsReview',
};

export function ComplianceStatusPip({ status }: { status: ComplianceState }) {
  return (
    <StatusPip state={COMPLIANCE_STATE_PIP[status]} labelKey={COMPLIANCE_STATE_LABEL_KEY[status]} />
  );
}
