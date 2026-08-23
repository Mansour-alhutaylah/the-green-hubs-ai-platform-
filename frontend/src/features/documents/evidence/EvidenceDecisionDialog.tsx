import { useEffect, useId, useRef, useState } from 'react';
import { Button, Dialog, Icon, Select } from '@/design-system';
import { useLocale } from '@/lib/i18n/useLocale';
import { ConflictError, ForbiddenError, RequestAbortedError, ValidationApiError } from '@/lib/api/errors';
import {
  rejectDocumentEvidence,
  restrictDocumentEvidence,
  supersedeDocumentEvidence,
  verifyDocumentEvidence,
} from '@/lib/api/endpoints/documents';
import type { DocumentReadResponse } from '@/lib/api/types';
import type { StringKey } from '@/lib/i18n/strings/en';
import {
  EvidenceCommand,
  MAX_REVIEW_REASON_CHARS,
  acceptsSuccessor,
  requiresReason,
} from './evidenceLifecycle';
import { useSuccessorCandidates } from './useSuccessorCandidates';

const TITLE_KEY: Record<EvidenceCommand, StringKey> = {
  [EvidenceCommand.Verify]: 'evidence.confirm.verify.title',
  [EvidenceCommand.Reject]: 'evidence.confirm.reject.title',
  [EvidenceCommand.Restrict]: 'evidence.confirm.restrict.title',
  [EvidenceCommand.Supersede]: 'evidence.confirm.supersede.title',
};

const DESCRIPTION_KEY: Record<EvidenceCommand, StringKey> = {
  [EvidenceCommand.Verify]: 'evidence.confirm.verify.description',
  [EvidenceCommand.Reject]: 'evidence.confirm.reject.description',
  [EvidenceCommand.Restrict]: 'evidence.confirm.restrict.description',
  [EvidenceCommand.Supersede]: 'evidence.confirm.supersede.description',
};

/** What the dialog is currently telling the reviewer about a failure.
 * `conflict` is kept distinct from `error` because it is the one failure
 * with a specific, useful next step — refresh and look again — rather than
 * "try that once more". */
type FailureKind = 'conflict' | 'forbidden' | 'error' | null;

export interface EvidenceDecisionDialogProps {
  command: EvidenceCommand;
  document: DocumentReadResponse;
  onClose: () => void;
  /** Re-fetches the authoritative document. Awaited before the dialog
   * closes, so the panel behind it never briefly shows the stale
   * decision. */
  onRecorded: () => Promise<void>;
  /** Refreshes the document after a conflict without recording anything. */
  onRefresh: () => Promise<void>;
}

/**
 * The confirmation step for one evidence decision.
 *
 * Every state-changing command goes through this dialog; none is applied
 * straight from a button in the panel. That is deliberate for a decision
 * that, once recorded, has no approved replacement path.
 *
 * Four properties this component exists to guarantee:
 *
 * 1. **Nothing is claimed before the server confirms it.** The panel is
 *    refreshed from the backend after a 2xx and only then does the dialog
 *    close. There is no optimistic status update anywhere in this flow.
 * 2. **The reviewer's reason is never silently discarded.** Every failure
 *    path leaves the dialog open with the typed reason intact — including
 *    a 409, where re-typing a paragraph of justification would be the
 *    interface punishing the reviewer for someone else's edit.
 * 3. **A pending request cannot be submitted twice.** The submit control
 *    is disabled while in flight and the handler returns early, so neither
 *    a double click nor a second Enter can produce two decisions.
 * 4. **Only the server's own safe message is shown.** The typed error
 *    classes carry the backend's `detail` string, which is written to be
 *    user-facing; no raw body, SQL, token or stack ever reaches the DOM.
 */
export function EvidenceDecisionDialog({
  command,
  document,
  onClose,
  onRecorded,
  onRefresh,
}: EvidenceDecisionDialogProps) {
  const { t } = useLocale();
  const fieldId = useId();
  const reasonId = `${fieldId}-reason`;
  const reasonHintId = `${fieldId}-reason-hint`;
  const reasonErrorId = `${fieldId}-reason-error`;
  const successorId = `${fieldId}-successor`;
  const successorHintId = `${fieldId}-successor-hint`;
  const failureId = `${fieldId}-failure`;

  const reasonRequired = requiresReason(command);
  const wantsSuccessor = acceptsSuccessor(command);

  const [reason, setReason] = useState('');
  const [successor, setSuccessor] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [reasonError, setReasonError] = useState<StringKey | null>(null);
  const [failure, setFailure] = useState<FailureKind>(null);
  const [failureDetail, setFailureDetail] = useState<string | null>(null);

  const reasonRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  useEffect(() => () => abortRef.current?.abort(), []);

  const successorState = useSuccessorCandidates(wantsSuccessor, document);

  function validate(): boolean {
    const trimmed = reason.trim();
    if (reasonRequired && !trimmed) {
      setReasonError('evidence.reason.error.required');
      reasonRef.current?.focus();
      return false;
    }
    if (trimmed.length > MAX_REVIEW_REASON_CHARS) {
      setReasonError('evidence.reason.error.tooLong');
      reasonRef.current?.focus();
      return false;
    }
    setReasonError(null);
    return true;
  }

  async function handleSubmit() {
    // The pending guard, stated first: a second submit while a request is
    // in flight must not reach the network at all.
    if (submitting) return;
    if (!validate()) return;

    const controller = new AbortController();
    abortRef.current = controller;
    setSubmitting(true);
    setFailure(null);
    setFailureDetail(null);

    const trimmed = reason.trim();

    try {
      switch (command) {
        case EvidenceCommand.Verify:
          await verifyDocumentEvidence(document.id, { reason: trimmed }, controller.signal);
          break;
        case EvidenceCommand.Reject:
          await rejectDocumentEvidence(document.id, { reason: trimmed }, controller.signal);
          break;
        case EvidenceCommand.Restrict:
          await restrictDocumentEvidence(document.id, { reason: trimmed }, controller.signal);
          break;
        case EvidenceCommand.Supersede:
          await supersedeDocumentEvidence(
            document.id,
            {
              reason: trimmed,
              // A document may never supersede itself. The candidate list
              // already excludes it; this refuses it a second time in case
              // the value ever arrives from anywhere else.
              supersededByDocumentId: successor && successor !== document.id ? successor : undefined,
            },
            controller.signal,
          );
          break;
      }

      // Only now is anything true. The authoritative document is re-read
      // before the dialog closes, so what the reviewer sees next is the
      // server's recorded decision rather than this component's hope.
      await onRecorded();
      onClose();
    } catch (error: unknown) {
      if (error instanceof RequestAbortedError) return;

      if (error instanceof ConflictError) {
        setFailure('conflict');
        setFailureDetail(error.message);
      } else if (error instanceof ValidationApiError) {
        setFailure('error');
        setFailureDetail(error.message);
      } else if (error instanceof ForbiddenError) {
        setFailure('forbidden');
        setFailureDetail(null);
      } else {
        setFailure('error');
        setFailureDetail(error instanceof Error ? error.message : null);
      }
      // The dialog stays open and `reason` is untouched: the reviewer's
      // words survive every failure.
    } finally {
      setSubmitting(false);
      abortRef.current = null;
    }
  }

  async function handleConflictRefresh() {
    await onRefresh();
    onClose();
  }

  const reasonLength = reason.trim().length;

  return (
    <Dialog
      open
      onOpenChange={(next) => {
        // Esc and overlay clicks are blocked while a request is in flight
        // (`preventClose`); this handles a deliberate close otherwise.
        if (!next && !submitting) onClose();
      }}
      title={t(TITLE_KEY[command])}
      description={t(DESCRIPTION_KEY[command])}
      preventClose={submitting}
      variant="form"
      footer={
        failure === 'conflict' ? (
          <>
            <Button variant="ghost" size="md" onClick={onClose}>
              {t('evidence.confirm.cancel')}
            </Button>
            <Button size="md" onClick={() => void handleConflictRefresh()}>
              <Icon name="refresh" size={15} />
              {t('evidence.error.conflict.refresh')}
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" size="md" onClick={onClose} disabled={submitting}>
              {t('evidence.confirm.cancel')}
            </Button>
            <Button
              size="md"
              isLoading={submitting}
              loadingLabel={t('evidence.confirm.submitting')}
              onClick={() => void handleSubmit()}
            >
              {t('evidence.confirm.submit')}
            </Button>
          </>
        )
      }
    >
      <div className="space-y-4">
        <div className="rounded-l border border-line-200 bg-tint-100 px-3 py-2">
          <p className="text-caption font-semibold text-gray-600">{t('evidence.confirm.document')}</p>
          {/* `break-words` rather than truncation: a reviewer confirming an
              irreversible decision must be able to read the whole filename,
              however long it is. */}
          <p className="mt-0.5 break-words text-meta font-bold text-ink-900" data-user-content>
            {document.filename}
          </p>
        </div>

        <div>
          <label htmlFor={reasonId} className="block text-meta font-semibold text-ink-900">
            {reasonRequired
              ? t('evidence.reason.label.required')
              : t('evidence.reason.label.optional')}
          </label>
          <p id={reasonHintId} className="mt-1 text-caption text-gray-600">
            {reasonRequired
              ? t('evidence.reason.hint.required')
              : t('evidence.reason.hint.optional')}
          </p>
          <textarea
            id={reasonId}
            ref={reasonRef}
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
              if (reasonError) setReasonError(null);
            }}
            rows={4}
            maxLength={MAX_REVIEW_REASON_CHARS}
            disabled={submitting}
            required={reasonRequired}
            aria-required={reasonRequired}
            aria-invalid={reasonError ? true : undefined}
            aria-describedby={reasonError ? `${reasonHintId} ${reasonErrorId}` : reasonHintId}
            className="mt-2 w-full rounded-m border border-line-300 bg-surface-0 p-3 text-meta text-ink-900 transition-colors placeholder:text-gray-400 focus:border-forest-900 disabled:bg-mist-50"
          />
          <p className="mt-1 text-caption text-gray-600">
            {t('evidence.reason.counter', {
              count: reasonLength,
              max: MAX_REVIEW_REASON_CHARS,
            })}
          </p>
          {reasonError && (
            <p
              id={reasonErrorId}
              role="alert"
              className="mt-1 flex items-start gap-1.5 text-caption font-semibold text-red-700"
            >
              <Icon name="circle-alert" size={14} className="mt-px shrink-0" />
              {t(reasonError, { max: MAX_REVIEW_REASON_CHARS })}
            </p>
          )}
        </div>

        {wantsSuccessor && (
          <div>
            <label htmlFor={successorId} className="block text-meta font-semibold text-ink-900">
              {t('evidence.successor.label')}
            </label>
            <p id={successorHintId} className="mt-1 text-caption text-gray-600">
              {t('evidence.successor.hint')}
            </p>
            <Select
              id={successorId}
              controlSize="md"
              className="mt-2 w-full"
              containerClassName="mt-0"
              value={successor}
              disabled={submitting || successorState.status === 'loading'}
              aria-describedby={successorHintId}
              onChange={(event) => setSuccessor(event.target.value)}
              options={[
                {
                  value: '',
                  label:
                    successorState.status === 'loading'
                      ? t('evidence.successor.loading')
                      : t('evidence.successor.none'),
                },
                ...successorState.candidates.map((candidate) => ({
                  value: candidate.id,
                  label: candidate.filename,
                })),
              ]}
            />
            {successorState.status === 'ready' && successorState.candidates.length === 0 && (
              <p className="mt-1 text-caption text-gray-600">{t('evidence.successor.empty')}</p>
            )}
          </div>
        )}

        {failure && (
          <div
            id={failureId}
            role="alert"
            className={
              failure === 'conflict'
                ? 'rounded-l border border-amber-100 bg-amber-100 p-3 text-amber-700'
                : 'rounded-l border border-red-100 bg-red-100 p-3 text-red-700'
            }
          >
            <p className="flex items-start gap-2 text-meta font-bold">
              <Icon name="circle-alert" size={15} className="mt-0.5 shrink-0" />
              {failure === 'conflict'
                ? t('evidence.error.conflict.title')
                : t('evidence.error.title')}
            </p>
            <p className="mt-1 text-caption">
              {failure === 'conflict'
                ? t('evidence.error.conflict.description')
                : failure === 'forbidden'
                  ? t('evidence.error.forbidden')
                  : /* The backend's own `detail`, which is written to be
                       shown to a user; `errors.ts` guarantees nothing else
                       reaches this string. */
                    (failureDetail ?? t('evidence.error.generic'))}
            </p>
          </div>
        )}
      </div>
    </Dialog>
  );
}
