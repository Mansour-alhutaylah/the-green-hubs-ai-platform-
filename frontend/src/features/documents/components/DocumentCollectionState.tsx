import type { ReactNode } from 'react';
import { EmptyState, LoadingSkeleton, SectionCard } from '@/design-system';

export type DocumentCollectionView = 'ready' | 'loading' | 'empty' | 'error';

export function DocumentCollectionState({
  state,
  children,
  emptyTitle = 'No documents in this demo workspace',
  emptyDescription = 'Upload will become available when the document service is connected.',
  emptyAction,
  errorTitle = 'Documents could not be displayed',
  errorDescription = 'This preview is unavailable. No backend request was attempted.',
  errorAction,
}: {
  state: DocumentCollectionView;
  children?: ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  errorTitle?: string;
  errorDescription?: string;
  errorAction?: ReactNode;
}) {
  if (state === 'loading') {
    return (
      <SectionCard
        className="mt-5 rounded-xl border-leaf-300/60 bg-mist-50"
        contentClassName="space-y-5"
        aria-live="polite"
        aria-busy="true"
      >
        {Array.from({ length: 4 }, (_, index) => (
          <LoadingSkeleton key={index} lines={2} label="Loading documents" />
        ))}
      </SectionCard>
    );
  }

  if (state === 'empty') {
    return (
      <SectionCard className="mt-5 rounded-xl border-leaf-300/60 bg-mist-50">
        <EmptyState title={emptyTitle} description={emptyDescription} action={emptyAction} />
      </SectionCard>
    );
  }

  if (state === 'error') {
    return (
      <SectionCard className="mt-5 rounded-xl border-red-100 bg-red-100/35" aria-live="assertive">
        <EmptyState title={errorTitle} description={errorDescription} action={errorAction} />
      </SectionCard>
    );
  }

  return <>{children}</>;
}
