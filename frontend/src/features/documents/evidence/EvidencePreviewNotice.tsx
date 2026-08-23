import { Icon, SectionCard } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';

/**
 * Preview's Evidence Review section.
 *
 * Preview is a self-contained demonstration: no backend, no Supabase, no
 * credentials, no stored data. An evidence decision is a *recorded,
 * attributable* act — it names a reviewer, a timestamp and a reason, and
 * it changes whether a document may be retrieved as evidence. There is
 * nothing in Preview for such a decision to be recorded against.
 *
 * So this renders no controls at all, rather than controls that would have
 * to pretend. A local demonstration that reset on reload was the
 * alternative, and it was rejected for one reason: the whole point of this
 * journey is that a decision is durable and attributable, and a
 * demonstration whose central property is falsified teaches the opposite
 * of what it appears to teach. A reviewer who clicked "Verify" here and
 * saw a verified badge would have been shown a claim this product cannot
 * make.
 *
 * Deliberately importing nothing from the Live path — no endpoint, no
 * hook, no fixture, no lifecycle contract. This component cannot issue a
 * request because it has no means to, not because a flag is switched off.
 */
export function EvidencePreviewNotice() {
  const { t } = useLocale();

  return (
    <SectionCard className="rounded-xl" title={t('evidence.section.title')}>
      <div className="rounded-l border border-line-200 bg-mist-50 p-4">
        <p className="flex items-start gap-2 text-meta font-bold text-ink-900">
          <Icon name="circle-alert" size={15} className="mt-0.5 shrink-0" aria-hidden />
          {t('evidence.preview.title')}
        </p>
        <p className="mt-1 text-caption text-gray-600">{t('evidence.preview.description')}</p>
      </div>
    </SectionCard>
  );
}
