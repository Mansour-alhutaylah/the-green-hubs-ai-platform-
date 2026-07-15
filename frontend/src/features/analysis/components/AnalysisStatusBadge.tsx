import { StatusBadge, type StatusTone } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import type { AnalysisRunStatus } from '../mockAnalysisData';

/** Accepts both the demo mock's `COMPLETE` and the live backend's real
 * `COMPLETED` (analysis_runs.status) — one badge for both modes. */
type BadgeStatus = AnalysisRunStatus | 'COMPLETED';

const TONES: Record<BadgeStatus, StatusTone> = {
  COMPLETE: 'success',
  COMPLETED: 'success',
  PROCESSING: 'processing',
  FAILED: 'danger',
  INSUFFICIENT_EVIDENCE: 'attention',
};

const LABEL_KEYS: Record<BadgeStatus, StringKey> = {
  COMPLETE: 'analysis.status.complete',
  COMPLETED: 'analysis.status.complete',
  PROCESSING: 'analysis.status.processing',
  FAILED: 'analysis.status.failed',
  INSUFFICIENT_EVIDENCE: 'analysis.status.insufficientEvidence',
};

export function AnalysisStatusBadge({ status }: { status: BadgeStatus }) {
  const { t } = useLocale();
  return <StatusBadge tone={TONES[status]}>{t(LABEL_KEYS[status])}</StatusBadge>;
}
