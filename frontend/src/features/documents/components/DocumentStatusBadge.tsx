import { StatusBadge, type StatusTone } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import type { StringKey } from '@/lib/i18n/strings/en';
import type { DocumentProcessingStatus } from '../mockDocuments';

const STATUS_TONES: Record<DocumentProcessingStatus, StatusTone> = {
  PENDING: 'pending',
  PROCESSING: 'processing',
  PROCESSED: 'success',
  FAILED: 'danger',
};

const LABEL_KEYS: Record<DocumentProcessingStatus, StringKey> = {
  PENDING: 'documents.status.pending',
  PROCESSING: 'documents.status.processing',
  PROCESSED: 'documents.status.processed',
  FAILED: 'documents.status.failed',
};

export function DocumentStatusBadge({ status }: { status: DocumentProcessingStatus }) {
  const { t } = useLocale();
  return <StatusBadge tone={STATUS_TONES[status]}>{t(LABEL_KEYS[status])}</StatusBadge>;
}
