import type { ReactNode } from 'react';
import { EmptyState, LoadingSkeleton, SectionCard } from '@/design-system';

export type DocumentCollectionView = 'ready' | 'loading' | 'empty' | 'error';

export function DocumentCollectionState({
  state,
  children,
}: {
  state: DocumentCollectionView;
  children?: ReactNode;
}) {
  if (state === 'loading') {
    return (
      <SectionCard className="mt-5" contentClassName="space-y-5" aria-live="polite">
        {Array.from({ length: 4 }, (_, index) => (
          <LoadingSkeleton key={index} lines={2} label="Loading documents" />
        ))}
      </SectionCard>
    );
  }

  if (state === 'empty') {
    return (
      <SectionCard className="mt-5">
        <EmptyState
          title="No documents in this demo workspace"
          description="Upload will become available when the document service is connected."
        />
      </SectionCard>
    );
  }

  if (state === 'error') {
    return (
      <SectionCard className="mt-5 border-red-100" aria-live="assertive">
        <EmptyState
          title="Documents could not be displayed"
          description="This preview is unavailable. No backend request was attempted."
        />
      </SectionCard>
    );
  }

  return <>{children}</>;
}
