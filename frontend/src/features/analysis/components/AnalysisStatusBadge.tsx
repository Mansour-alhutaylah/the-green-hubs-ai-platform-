import { StatusBadge, type StatusTone } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import type { AnalysisRunStatus } from '../mockAnalysisData';

const TONES: Record<AnalysisRunStatus, StatusTone> = {
  COMPLETE: 'success',
  PROCESSING: 'processing',
  FAILED: 'danger',
  INSUFFICIENT_EVIDENCE: 'attention',
};

const LABEL_KEYS: Record<AnalysisRunStatus, StringKey> = {
  COMPLETE: 'analysis.status.complete',
  PROCESSING: 'analysis.status.processing',
  FAILED: 'analysis.status.failed',
  INSUFFICIENT_EVIDENCE: 'analysis.status.insufficientEvidence',
};

export function AnalysisStatusBadge({ status }: { status: AnalysisRunStatus }) {
  const { t } = useLocale();
  return <StatusBadge tone={TONES[status]}>{t(LABEL_KEYS[status])}</StatusBadge>;
}
