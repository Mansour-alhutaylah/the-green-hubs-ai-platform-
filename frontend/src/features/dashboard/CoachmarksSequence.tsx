import { useEffect, useState } from 'react';
import { useLocale } from '@/lib/i18n/useLocale';
import { DiamondGlyph } from '@/design-system';

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
 */
export function CoachmarksSequence() {
  const { t } = useLocale();
  const [visible, setVisible] = useState(() => !hasOnboarded());

  useEffect(() => {
    if (!visible) return;

    function dismiss() {
      window.localStorage.setItem(ONBOARDED_KEY, '1');
      setVisible(false);
    }

    // Any interaction elsewhere in the app dismisses the sequence for good.
    window.addEventListener('pointerdown', dismiss, { capture: true });
    window.addEventListener('keydown', dismiss, { capture: true });
    return () => {
      window.removeEventListener('pointerdown', dismiss, { capture: true });
      window.removeEventListener('keydown', dismiss, { capture: true });
    };
  }, [visible]);

  if (!visible) return null;

  const steps = [
    t('coachmarks.orgSwitcher'),
    t('coachmarks.insightLedger'),
    t('coachmarks.uploadEntry'),
  ];

  return (
    // Capped to the viewport's safe area so the panel cannot sit on top of
    // a table, a chart label, or the last card in a column.
    // `max-w-[calc(100vw-2rem)]` keeps it inside a 360px screen, where the
    // old fixed `w-80` (320px) plus a 24px inset came within a few pixels
    // of the edge. The dashboard reserves matching bottom padding, so the
    // panel overlays empty space rather than content.
    <output className="fixed bottom-4 end-4 z-[var(--z-overlay)] block w-80 max-w-[calc(100vw-2rem)] rounded-m bg-forest-900 p-4 text-white shadow-float sm:bottom-6 sm:end-6">
      <ul className="flex flex-col gap-3">
        {steps.map((step) => (
          <li key={step} className="flex items-start gap-2 text-meta">
            <DiamondGlyph variant="filled" size={7} className="mt-1 text-leaf-500" />
            <span>{step}</span>
          </li>
        ))}
      </ul>
    </output>
  );
}
