import { StatusBadge, type StatusTone } from '@/design-system';
import type { DocumentProcessingStatus } from '../mockDocuments';

const STATUS_TONES: Record<DocumentProcessingStatus, StatusTone> = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  PROCESSED: 'success',
  FAILED: 'danger',
};

export function DocumentStatusBadge({ status }: { status: DocumentProcessingStatus }) {
  return <StatusBadge tone={STATUS_TONES[status]}>{status}</StatusBadge>;
}
