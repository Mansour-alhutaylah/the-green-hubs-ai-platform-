import { useCallback, useRef, useState } from 'react';
import { Icon, SectionCard, StatusBadge, type StatusTone } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { formatDateTime } from '@/lib/utils/formatDate';
import { Permission } from '@/features/rbac/permissions';
import { useHasPermission } from '@/features/rbac/useHasPermission';
import type { DocumentReadResponse, EvidenceStatus } from '@/lib/api/types';
import type { StringKey } from '@/lib/i18n/strings/en';
import {
  EVIDENCE_COMMANDS,
  EvidenceCommand,
  commandBlocker,
  hasAnyAvailableCommand,
  isRetrievalEligible,
} from './evidenceLifecycle';
import { EvidenceDecisionDialog } from './EvidenceDecisionDialog';

const STATUS_LABEL_KEY: Record<EvidenceStatus, StringKey> = {
  PENDING_REVIEW: 'evidence.status.PENDING_REVIEW',
  VERIFIED: 'evidence.status.VERIFIED',
  REJECTED: 'evidence.status.REJECTED',
  RESTRICTED: 'evidence.status.RESTRICTED',
  SUPERSEDED: 'evidence.status.SUPERSEDED',
};

const STATUS_DETAIL_KEY: Record<EvidenceStatus, StringKey> = {
  PENDING_REVIEW: 'evidence.status.detail.PENDING_REVIEW',
  VERIFIED: 'evidence.status.detail.VERIFIED',
  REJECTED: 'evidence.status.detail.REJECTED',
  RESTRICTED: 'evidence.status.detail.RESTRICTED',
  SUPERSEDED: 'evidence.status.detail.SUPERSEDED',
};

/** Tone is a redundant cue only. Every badge also carries its own text and
 * a distinct glyph, so no state is communicated by color alone. */
const STATUS_TONE: Record<EvidenceStatus, StatusTone> = {
  PENDING_REVIEW: 'pending',
  VERIFIED: 'success',
  REJECTED: 'danger',
  RESTRICTED: 'attention',
  SUPERSEDED: 'neutral',
};

const ACTION_LABEL_KEY: Record<EvidenceCommand, StringKey> = {
  [EvidenceCommand.Verify]: 'evidence.action.verify',
  [EvidenceCommand.Reject]: 'evidence.action.reject',
  [EvidenceCommand.Restrict]: 'evidence.action.restrict',
  [EvidenceCommand.Supersede]: 'evidence.action.supersede',
};

const ACTION_DESCRIPTION_KEY: Record<EvidenceCommand, StringKey> = {
  [EvidenceCommand.Verify]: 'evidence.action.verify.description',
  [EvidenceCommand.Reject]: 'evidence.action.reject.description',
  [EvidenceCommand.Restrict]: 'evidence.action.restrict.description',
  [EvidenceCommand.Supersede]: 'evidence.action.supersede.description',
};

const BLOCKER_KEY = {
  'already-in-state': 'evidence.blocked.already-in-state',
  'decision-recorded': 'evidence.blocked.decision-recorded',
  'not-processed': 'evidence.blocked.not-processed',
} as const satisfies Record<string, StringKey>;

export interface EvidenceReviewPanelProps {
  document: DocumentReadResponse;
  /** Re-fetches the authoritative document from the backend. */
  onRefresh: () => Promise<void>;
}

/**
 * The Live evidence-review journey for one document.
 *
 * Everything rendered here is a value the server returned. The status, the
 * reviewer, the timestamp, the reason and the successor are read straight
 * off the document; where the backend recorded nothing, this says so
 * rather than inventing a reviewer or a date. A document in
 * `PENDING_REVIEW` genuinely has no provenance — nobody has decided
 * anything yet — and displaying a blank-but-present "Decided by" row would
 * be fabricating one.
 *
 * **Two independent conditions gate every control**: the reviewer's role
 * must hold `evidence.review` (a shared policy table, never a role-name
 * comparison written here), and the document's current state must permit
 * that specific command. Both are also enforced by the backend, which is
 * the actual security boundary — a reviewer who bypasses this UI entirely
 * is refused with 403 or 409 by the server. What this component decides is
 * only what is worth offering.
 *
 * A denied reviewer is told the truth — their role cannot make evidence
 * decisions — and is shown the recorded decision read-only. No disabled
 * action buttons are rendered for them at all, so there is nothing to
 * click, and nothing that could dispatch a request.
 */
export function EvidenceReviewPanel({ document, onRefresh }: EvidenceReviewPanelProps) {
  const { t } = useLocale();
  const canReview = useHasPermission(Permission.EvidenceReview);
  const [activeCommand, setActiveCommand] = useState<EvidenceCommand | null>(null);

  /**
   * The control that opened the dialog, so focus can be returned to it.
   *
   * Radix restores focus to its trigger on close, but only while the
   * dialog is still mounted; this panel unmounts the whole dialog the
   * moment `activeCommand` clears, which cuts that restoration short. A
   * keyboard user would otherwise be dropped at the top of the document
   * after every cancelled decision, so the panel restores focus itself.
   */
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const closeDialog = useCallback(() => {
    setActiveCommand(null);
    const trigger = triggerRef.current;
    triggerRef.current = null;
    // After the dialog has unmounted, so nothing steals the focus back.
    requestAnimationFrame(() => trigger?.focus());
  }, []);

  const status = document.evidence_status;
  const processingStatus = document.processing_status;
  const eligible = isRetrievalEligible(status);
  const anyAvailable = hasAnyAvailableCommand(status, processingStatus);
  const decided = status !== 'PENDING_REVIEW';

  return (
    <SectionCard
      className="rounded-xl"
      title={t('evidence.section.title')}
      description={t('evidence.section.description')}
      contentClassName="space-y-4"
    >
      {/* A named live region: a decision recorded elsewhere in the page
          updates this text, and a screen-reader user is told so. */}
      <section
        aria-label={t('evidence.status.label')}
        aria-live="polite"
        className="rounded-l border border-line-200 bg-tint-100 p-4"
      >
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone={STATUS_TONE[status]}>{t(STATUS_LABEL_KEY[status])}</StatusBadge>
          <span className="inline-flex items-center gap-1.5 text-caption font-semibold text-gray-600">
            <Icon name={eligible ? 'check' : 'circle-alert'} size={13} aria-hidden />
            {eligible ? t('evidence.retrieval.eligible') : t('evidence.retrieval.ineligible')}
          </span>
        </div>
        <p className="mt-2 text-meta text-gray-600">{t(STATUS_DETAIL_KEY[status])}</p>
      </section>

      <dl className="divide-y divide-line-200">
        <ProvenanceRow
          label={t('evidence.provenance.processingStatus')}
          value={processingStatus ?? '—'}
        />
        {decided ? (
          <>
            <ProvenanceRow
              label={t('evidence.provenance.reviewedBy')}
              value={document.reviewed_by ?? '—'}
              monospace
            />
            <ProvenanceRow
              label={t('evidence.provenance.reviewedAt')}
              value={document.reviewed_at ? formatDateTime(document.reviewed_at) : '—'}
            />
            <ProvenanceRow
              label={t('evidence.provenance.reason')}
              value={document.review_reason ?? t('evidence.provenance.noReason')}
            />
            {status === 'SUPERSEDED' && (
              <ProvenanceRow
                label={t('evidence.provenance.successor')}
                value={
                  document.superseded_by_document_id ?? t('evidence.provenance.noSuccessor')
                }
                monospace={document.superseded_by_document_id != null}
              />
            )}
          </>
        ) : (
          <div className="py-3 first:pt-0 last:pb-0">
            <p className="text-caption text-gray-600">{t('evidence.provenance.none')}</p>
          </div>
        )}
      </dl>

      {!canReview ? (
        <div className="rounded-l border border-line-200 bg-mist-50 p-4">
          <p className="flex items-start gap-2 text-meta font-bold text-ink-900">
            <Icon name="circle-alert" size={15} className="mt-0.5 shrink-0" aria-hidden />
            {t('evidence.denied.title')}
          </p>
          <p className="mt-1 text-caption text-gray-600">{t('evidence.denied.description')}</p>
        </div>
      ) : anyAvailable ? (
        <div>
          <h3 className="text-meta font-bold text-ink-900">{t('evidence.actions.label')}</h3>
          <ul className="mt-2 space-y-2" aria-label={t('evidence.actions.label')}>
            {EVIDENCE_COMMANDS.map((command) => {
              const blocker = commandBlocker(command, status, processingStatus);
              if (blocker !== null) {
                // Unavailable commands are explained, not hidden: knowing
                // *why* verify is unavailable is the difference between an
                // interface that reads as considered and one that reads as
                // arbitrary. Nothing here is clickable.
                return (
                  <li
                    key={command}
                    className="rounded-l border border-line-200 bg-mist-50 px-3 py-2"
                  >
                    <p className="text-meta font-semibold text-gray-600">
                      {t(ACTION_LABEL_KEY[command])}
                    </p>
                    <p className="mt-0.5 text-caption text-gray-600">{t(BLOCKER_KEY[blocker])}</p>
                  </li>
                );
              }
              return (
                <li key={command}>
                  <button
                    type="button"
                    onClick={(event) => {
                      triggerRef.current = event.currentTarget;
                      setActiveCommand(command);
                    }}
                    className="w-full rounded-l border border-line-200 bg-surface-0 px-3 py-2 text-start transition-colors hover:border-leaf-300 hover:bg-tint-100"
                  >
                    <span className="flex items-center gap-2 text-meta font-bold text-forest-900">
                      <Icon name="check" size={14} className="shrink-0" aria-hidden />
                      {t(ACTION_LABEL_KEY[command])}
                    </span>
                    <span className="mt-0.5 block text-caption text-gray-600">
                      {t(ACTION_DESCRIPTION_KEY[command])}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <div className="rounded-l border border-line-200 bg-mist-50 p-4">
          <p className="text-meta font-bold text-ink-900">{t('evidence.settled.title')}</p>
          <p className="mt-1 text-caption text-gray-600">{t('evidence.settled.description')}</p>
        </div>
      )}

      {activeCommand && (
        <EvidenceDecisionDialog
          command={activeCommand}
          document={document}
          onClose={closeDialog}
          onRecorded={onRefresh}
          onRefresh={onRefresh}
        />
      )}
    </SectionCard>
  );
}

function ProvenanceRow({
  label,
  value,
  monospace,
}: {
  label: string;
  value: string;
  monospace?: boolean;
}) {
  return (
    <div className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <dt className="text-meta text-gray-600">{label}</dt>
      {/* `break-words` and no truncation: a long recorded reason is the
          substance of the decision, and a reader must be able to see all of
          it rather than an ellipsis. */}
      <dd
        className={`min-w-0 break-words text-meta font-semibold text-ink-900 sm:max-w-[60%] sm:text-end${
          monospace ? ' font-mono text-caption' : ''
        }`}
        data-user-content
        dir={monospace ? 'ltr' : undefined}
      >
        {value}
      </dd>
    </div>
  );
}
