import { useEffect, useRef, useState } from 'react';
import { getDocument } from '@/lib/api/endpoints/documents';
import type { DocumentReadResponse } from '@/lib/api/types';

const POLL_INTERVAL_MS = 2000;
/** ~60s bounded — Sprint 4A requires a bounded maximum duration, then a
 * manual Refresh action instead of polling forever. */
const MAX_POLL_ATTEMPTS = 30;

export interface DocumentProcessingPollState {
  polling: boolean;
  timedOut: boolean;
}

/**
 * Bounded polling for a document stuck in `PROCESSING` — relevant only
 * when *this* browser observes that state via `GET`, since
 * `POST /process` itself is synchronous and already returns the terminal
 * state to whichever tab triggered it (see documents.ts). A refresh mid
 *-flight, or another tab/session processing the same document, are the
 * real cases this recovers: `PROCESSING` is confirmed live rather than
 * assumed to still be running in this tab's memory.
 *
 * No overlapping requests (each poll only schedules the next one after
 * the previous settles), pauses while the tab is hidden and resumes on
 * visibility, and stops immediately once the fetched status leaves
 * `PROCESSING`. Cleans up (aborts the in-flight request, clears the
 * timer) on unmount or whenever `documentId` changes.
 */
export function useDocumentProcessingPoll(
  documentId: string | undefined,
  currentDocument: DocumentReadResponse | null,
  onUpdate: (document: DocumentReadResponse) => void,
): DocumentProcessingPollState {
  const [timedOut, setTimedOut] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const shouldPoll = Boolean(documentId) && currentDocument?.processing_status === 'PROCESSING';

  useEffect(() => {
    if (!shouldPoll || !documentId) {
      setTimedOut(false);
      return;
    }
    const confirmedId = documentId;

    let cancelled = false;
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;

    function poll() {
      if (cancelled) return;
      if (window.document.visibilityState === 'hidden') {
        // Paused while hidden — `handleVisibilityChange` below resumes.
        return;
      }
      attempts += 1;
      if (attempts > MAX_POLL_ATTEMPTS) {
        setTimedOut(true);
        return;
      }
      controller = new AbortController();
      getDocument(confirmedId, controller.signal)
        .then((next) => {
          if (cancelled) return;
          onUpdateRef.current(next);
          if (next.processing_status === 'PROCESSING') {
            timer = setTimeout(poll, POLL_INTERVAL_MS);
          }
        })
        .catch(() => {
          if (!cancelled) timer = setTimeout(poll, POLL_INTERVAL_MS);
        });
    }

    function handleVisibilityChange() {
      if (!cancelled && window.document.visibilityState === 'visible') {
        if (timer !== undefined) clearTimeout(timer);
        poll();
      }
    }

    window.document.addEventListener('visibilitychange', handleVisibilityChange);
    timer = setTimeout(poll, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      if (timer !== undefined) clearTimeout(timer);
      controller?.abort();
      window.document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [shouldPoll, documentId]);

  return { polling: shouldPoll && !timedOut, timedOut };
}
