import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router';
import { useHasMinTier } from '@/features/rbac/useHasMinTier';
import { findNavItem } from '@/app/navigation/navConfig';
import { ROUTES } from '@/app/navigation/routePaths';

const G_CHORD_TIMEOUT_MS = 800;

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable;
}

/**
 * §3.3: "g" then "d/o/u/r" jumps to Dashboard/Organizations/Upload/Reports;
 * Esc closing overlays is handled per-overlay by Radix's own Escape
 * handling, so it isn't duplicated here.
 *
 * The "/" shortcut is deliberately absent. It used to focus the Context
 * Bar's search box, but nothing ever searched — the shortcut's only effect
 * was to make a non-functional input look live. Global search returns with
 * real Retrieval in F2, and the shortcut returns with it.
 */
export function useGlobalShortcuts(): void {
  const navigate = useNavigate();
  const canUpload = useHasMinTier(findNavItem('upload').minTier);
  const awaitingSecondKey = useRef(false);
  const chordTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (isTypingTarget(event.target)) return;

      if (awaitingSecondKey.current) {
        awaitingSecondKey.current = false;
        window.clearTimeout(chordTimer.current);
        switch (event.key) {
          case 'd':
            navigate(ROUTES.dashboard);
            break;
          case 'o':
            navigate(ROUTES.organizations);
            break;
          case 'u':
            if (canUpload) navigate(ROUTES.documentUpload);
            break;
          case 'r':
            navigate(ROUTES.reports);
            break;
          default:
            break;
        }
        return;
      }

      if (event.key === 'g') {
        awaitingSecondKey.current = true;
        chordTimer.current = window.setTimeout(() => {
          awaitingSecondKey.current = false;
        }, G_CHORD_TIMEOUT_MS);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.clearTimeout(chordTimer.current);
    };
  }, [navigate, canUpload]);
}
