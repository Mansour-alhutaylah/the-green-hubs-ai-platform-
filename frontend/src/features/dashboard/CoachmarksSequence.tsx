import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useLocale } from '@/lib/i18n/useLocale';
import { DiamondGlyph, Icon } from '@/design-system';
import { useIsCompactViewport } from '@/shell/useIsCompactViewport';

const ONBOARDED_KEY = 'ghp:has-onboarded';

function hasOnboarded(): boolean {
  return window.localStorage.getItem(ONBOARDED_KEY) === '1';
}

/**
 * §9.1/§18: "exactly three, on the first dashboard visit: org switcher,
 * Insight Ledger, upload entry. Forest popovers, dismiss-on-any-interaction,
 * never reappear." Phase 1 simplification: since the Insight Ledger and a
 * role-conditional Upload entry don't exist as business content yet, the
 * three tips render as one sequential Forest card (rather than three
 * separately anchored popovers pointing at not-yet-built UI) and dismiss on
 * the first click/keydown anywhere in the app — precise DOM-anchoring can
 * follow once those target elements carry real content in a later phase.
 *
 * ## Two presentations, because one of them was obstructing the page
 *
 * Above 480px the panel is unchanged: it appears on the first dashboard
 * visit, sits in the bottom-end corner, and dismisses on the first
 * interaction anywhere. That is the behaviour the spec describes and it
 * works when there is room beside the content for it.
 *
 * At 480px and below there is no such room. The panel is roughly 320px
 * wide on a 360px screen, so it covered whatever occupied the bottom of
 * the viewport, and because it only dismissed on interaction it sat on top
 * of the header, the primary actions, or a KPI card depending on scroll
 * position. Capping its width, which an earlier pass did, made it fit the
 * screen without making it stop covering things.
 *
 * So on a compact viewport it starts **closed** behind a named trigger and
 * opens as a bottom sheet the reader controls: Escape closes it, an
 * explicit Close button closes it, and focus moves into the sheet on open
 * and back to the trigger on close. Nothing is auto-shown and nothing is
 * covered until the reader asks for it.
 *
 * The coaching content is identical in both, and dismissing it in either
 * writes the same `ghp:has-onboarded` flag, so a reader who dismisses on a
 * phone does not meet the tips again on a laptop.
 */
export function CoachmarksSequence() {
  const { t } = useLocale();
  const compact = useIsCompactViewport();
  const [dismissed, setDismissed] = useState(() => hasOnboarded());

  const dismiss = useCallback(() => {
    window.localStorage.setItem(ONBOARDED_KEY, '1');
    setDismissed(true);
  }, []);

  if (dismissed) return null;

  const steps = [
    t('coachmarks.orgSwitcher'),
    t('coachmarks.insightLedger'),
    t('coachmarks.uploadEntry'),
  ];

  return compact ? (
    <CompactCoachmarks steps={steps} onDismiss={dismiss} />
  ) : (
    <FloatingCoachmarks steps={steps} onDismiss={dismiss} />
  );
}

/**
 * The unchanged desktop and tablet presentation: shown on arrival,
 * dismissed by the first interaction anywhere in the app.
 */
function FloatingCoachmarks({
  steps,
  onDismiss,
}: {
  steps: readonly string[];
  onDismiss: () => void;
}) {
  useEffect(() => {
    // Any interaction elsewhere in the app dismisses the sequence for good.
    window.addEventListener('pointerdown', onDismiss, { capture: true });
    window.addEventListener('keydown', onDismiss, { capture: true });
    return () => {
      window.removeEventListener('pointerdown', onDismiss, { capture: true });
      window.removeEventListener('keydown', onDismiss, { capture: true });
    };
  }, [onDismiss]);

  return (
    <output className="fixed bottom-4 end-4 z-[var(--z-overlay)] block w-80 max-w-[calc(100vw-2rem)] rounded-m bg-forest-900 p-4 text-white shadow-float sm:bottom-6 sm:end-6">
      <CoachmarkList steps={steps} />
    </output>
  );
}

/**
 * The compact presentation: closed by default, opened deliberately.
 *
 * There is no dismiss-on-any-interaction listener here, and that is the
 * point rather than an omission. The reader opened this on purpose, so
 * closing it on their next tap would make it impossible to read, and the
 * global listener would fire on the very tap that opened it.
 */
function CompactCoachmarks({
  steps,
  onDismiss,
}: {
  steps: readonly string[];
  onDismiss: () => void;
}) {
  const { t } = useLocale();
  const [open, setOpen] = useState(false);
  const sheetId = useId();
  const headingId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    // Focus returns to the control that opened the sheet, so a keyboard
    // reader is not dropped at the top of the document.
    triggerRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    // Focus moves into the sheet on open, onto the control that closes it.
    closeRef.current?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation();
        close();
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, close]);

  return (
    <>
      {/* Small enough to clear a 360px screen, and the only thing rendered
          until the reader asks for more. */}
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={open}
        aria-controls={open ? sheetId : undefined}
        onClick={() => setOpen((current) => !current)}
        className="fixed bottom-4 end-4 z-[var(--z-overlay)] inline-flex min-h-10 items-center gap-2 rounded-full bg-forest-900 px-4 text-meta font-bold text-white shadow-float focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
      >
        <DiamondGlyph variant="filled" size={7} className="text-leaf-500" />
        {t('coachmarks.trigger')}
      </button>

      {open && (
        /* A native non-modal `<dialog open>`, not a `div` with
           `role="dialog"`: the element carries the semantics itself, and
           non-modal is deliberate. This sheet must not trap focus or
           inert the page behind it, because the reader should be able to
           keep using the dashboard with the tips open.

           Bottom-anchored and height-capped, so even at full extension it
           leaves the upper viewport, and therefore the page heading and
           the primary actions, visible behind it. It scrolls internally
           rather than growing past the screen. */
        <dialog
          open
          id={sheetId}
          aria-labelledby={headingId}
          className="fixed inset-x-3 bottom-3 top-auto z-[var(--z-dialog)] m-0 max-h-[60vh] w-auto max-w-none overflow-y-auto overscroll-contain rounded-m bg-forest-900 p-4 text-white shadow-float"
        >
          <div className="flex items-start justify-between gap-3">
            <h2 id={headingId} className="text-body font-bold text-white">
              {t('coachmarks.title')}
            </h2>
            <button
              ref={closeRef}
              type="button"
              onClick={close}
              className="-me-1 -mt-1 shrink-0 rounded-s p-1.5 text-white/80 transition-colors hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-leaf-500"
            >
              <Icon name="x" size={16} />
              <span className="sr-only">{t('coachmarks.close')}</span>
            </button>
          </div>

          <div className="mt-3">
            <CoachmarkList steps={steps} />
          </div>

          <button
            type="button"
            onClick={onDismiss}
            className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-m border border-white/20 bg-white/7 px-4 text-meta font-bold text-white transition-colors hover:bg-white/12 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-leaf-500"
          >
            {t('coachmarks.dismiss')}
          </button>
        </dialog>
      )}
    </>
  );
}

function CoachmarkList({ steps }: { steps: readonly string[] }) {
  return (
    <ul className="flex flex-col gap-3">
      {steps.map((step) => (
        <li key={step} className="flex items-start gap-2 text-meta">
          <DiamondGlyph variant="filled" size={7} className="mt-1 text-leaf-500" />
          <span>{step}</span>
        </li>
      ))}
    </ul>
  );
}
