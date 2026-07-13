import { StatusBadge, type StatusTone } from '@/design-system';
import type { AnalysisRunStatus } from '../mockAnalysisData';

const TONES: Record<AnalysisRunStatus, StatusTone> = {
  COMPLETE: 'success',
  PROCESSING: 'processing',
  FAILED: 'danger',
};

export function AnalysisStatusBadge({ status }: { status: AnalysisRunStatus }) {
  return <StatusBadge tone={TONES[status]}>{status}</StatusBadge>;
}
