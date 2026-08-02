import { useEffect, useRef, useState } from 'react';
import { getAnalysisRun } from '@/lib/api/endpoints/analysis';
import type { AnalysisRunResponse } from '@/lib/api/types';

const POLL_INTERVAL_MS = 2000;
/** ~60s bounded — after that a manual Refresh action takes over instead of
 * polling forever. */
const MAX_POLL_ATTEMPTS = 30;

export interface AnalysisRunPollState {
  polling: boolean;
  timedOut: boolean;
}

/**
 * Bounded polling for an analysis run observed in `PROCESSING` — needed
 * only when *this* browser sees that state via `GET`, since the analyze
 * POST itself is synchronous on this backend and normally returns a
 * terminal status to whichever tab triggered it. A refresh mid-flight, or
 * an identical request running in another session, are the real cases
 * this recovers.
 *
 * Mirrors `useDocumentProcessingPoll`: no overlapping requests (each poll
 * schedules the next only after the previous settles), pauses while the
 * tab is hidden and resumes on visibility, stops immediately once the
 * fetched status leaves `PROCESSING` (COMPLETED / FAILED /
 * INSUFFICIENT_EVIDENCE / anything unknown), and cleans up — aborting the
 * in-flight request and clearing the timer — on unmount, logout-driven
 * route change, or whenever `runId` changes. It never starts a second
 * analysis; it only reads the existing run.
 */
export function useAnalysisRunPoll(
  runId: string | undefined,
  currentRun: AnalysisRunResponse | null,
  onUpdate: (run: AnalysisRunResponse) => void,
): AnalysisRunPollState {
  const [timedOut, setTimedOut] = useState(false);
  const onUpdateRef = useRef(onUpdate);
  onUpdateRef.current = onUpdate;

  const shouldPoll = Boolean(runId) && currentRun?.status === 'PROCESSING';

  useEffect(() => {
    if (!shouldPoll || !runId) {
      setTimedOut(false);
      return;
    }
    const confirmedId = runId;

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
      getAnalysisRun(confirmedId, controller.signal)
        .then((next) => {
          if (cancelled) return;
          onUpdateRef.current(next);
          if (next.status === 'PROCESSING') {
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
  }, [shouldPoll, runId]);

  return { polling: shouldPoll && !timedOut, timedOut };
}
