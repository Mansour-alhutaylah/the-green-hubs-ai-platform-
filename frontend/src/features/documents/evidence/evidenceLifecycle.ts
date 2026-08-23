/**
 * The frontend mirror of the evidence-review state machine
 * (`backend/app/domain/evidence/lifecycle.py`).
 *
 * **The backend is the authority.** Every rule here is also enforced
 * server-side, inside the same conditional UPDATE that performs the
 * transition. What this module decides is only which controls are worth
 * *offering*: a reviewer should not be handed a "Verify" button that the
 * server will answer with 409 because the document was rejected last week.
 * Offering an impossible action is a UX defect; refusing it is the
 * backend's job, and it does that whatever this file says.
 *
 * It is a transcription, not a second opinion. Nothing here may be
 * loosened to make a control appear: if this table and the backend ever
 * disagree, the visible symptom is a 409 the panel already renders
 * truthfully, and the fix is to correct this table.
 *
 * The five states are **not a sequence**. They are five distinct business
 * outcomes, and treating them as a pipeline — assuming SUPERSEDED is
 * "later" than RESTRICTED, or that a document must be VERIFIED before it
 * can be REJECTED — is exactly the misreading the backend module warns
 * against.
 */
import type { EvidenceStatus } from '@/lib/api/types';

export const EvidenceCommand = {
  Verify: 'verify',
  Reject: 'reject',
  Restrict: 'restrict',
  Supersede: 'supersede',
} as const;

export type EvidenceCommand = (typeof EvidenceCommand)[keyof typeof EvidenceCommand];

/** Declaration order — also the order the controls are presented in. */
export const EVIDENCE_COMMANDS: readonly EvidenceCommand[] = [
  EvidenceCommand.Verify,
  EvidenceCommand.Reject,
  EvidenceCommand.Restrict,
  EvidenceCommand.Supersede,
];

/** The state each command records when it succeeds. */
const COMMAND_TARGET_STATUS: Readonly<Record<EvidenceCommand, EvidenceStatus>> = {
  [EvidenceCommand.Verify]: 'VERIFIED',
  [EvidenceCommand.Reject]: 'REJECTED',
  [EvidenceCommand.Restrict]: 'RESTRICTED',
  [EvidenceCommand.Supersede]: 'SUPERSEDED',
};

/**
 * From each state, the commands that may genuinely change it.
 *
 * Withdrawal is supported; reactivation is not. A VERIFIED document can be
 * withdrawn to REJECTED, RESTRICTED or SUPERSEDED when new information
 * appears. The reverse is refused: there is no approved re-review command,
 * and letting a second `verify` undo a rejection would make the rejection
 * decorative.
 *
 * The three decided states are terminal for *every* command, not only for
 * verify. All three are already retrieval-ineligible, so nothing unsafe is
 * preserved by refusing; what is preserved is the recorded decision.
 */
const ALLOWED_TRANSITIONS: Readonly<Record<EvidenceStatus, readonly EvidenceCommand[]>> = {
  PENDING_REVIEW: [
    EvidenceCommand.Verify,
    EvidenceCommand.Reject,
    EvidenceCommand.Restrict,
    EvidenceCommand.Supersede,
  ],
  VERIFIED: [EvidenceCommand.Reject, EvidenceCommand.Restrict, EvidenceCommand.Supersede],
  REJECTED: [],
  RESTRICTED: [],
  SUPERSEDED: [],
};

/** Commands whose reason is mandatory. Verify's note is optional: an
 * approval's meaning is the approval, whereas a refusal, restriction or
 * supersession is not interpretable without a stated reason. */
const REASON_REQUIRED: readonly EvidenceCommand[] = [
  EvidenceCommand.Reject,
  EvidenceCommand.Restrict,
  EvidenceCommand.Supersede,
];

/** Matches the backend's `MAX_REVIEW_REASON_CHARS`. A review
 * justification, not a comment thread. */
export const MAX_REVIEW_REASON_CHARS = 1000;

/** The `processing_status` a document must hold before it may be approved.
 * Only verify constrains it: approving a document asserts something about
 * content that does not exist until extraction and chunking complete. The
 * three withdrawal commands deliberately carry no such precondition — a
 * document whose extraction FAILED is exactly the kind that needs
 * rejecting, and a precondition there would strand it forever. */
const PROCESSED_PROCESSING_STATUS = 'PROCESSED';

/** The only retrieval-eligible state. Every other state — including the
 * initial one — is ineligible, so retrieval fails closed for anything a
 * human has not explicitly approved. */
export function isRetrievalEligible(status: EvidenceStatus): boolean {
  return status === 'VERIFIED';
}

export function requiresReason(command: EvidenceCommand): boolean {
  return REASON_REQUIRED.includes(command);
}

export function acceptsSuccessor(command: EvidenceCommand): boolean {
  return command === EvidenceCommand.Supersede;
}

export function targetStatusFor(command: EvidenceCommand): EvidenceStatus {
  return COMMAND_TARGET_STATUS[command];
}

/** Why a command is unavailable, or `null` when it is available.
 *
 * Distinguishing the reasons is the point: "already in this state" and
 * "this document was decided and cannot be re-decided" and "not processed
 * yet" are three different things to tell a reviewer, and collapsing them
 * into a disabled button with no explanation is what makes an interface
 * feel arbitrary. */
export type EvidenceCommandBlocker = 'already-in-state' | 'decision-recorded' | 'not-processed';

export function commandBlocker(
  command: EvidenceCommand,
  currentStatus: EvidenceStatus,
  processingStatus: string | null,
): EvidenceCommandBlocker | null {
  if (currentStatus === targetStatusFor(command)) return 'already-in-state';
  if (!ALLOWED_TRANSITIONS[currentStatus]?.includes(command)) return 'decision-recorded';
  if (
    command === EvidenceCommand.Verify &&
    processingStatus !== PROCESSED_PROCESSING_STATUS
  ) {
    return 'not-processed';
  }
  return null;
}

export function isCommandAvailable(
  command: EvidenceCommand,
  currentStatus: EvidenceStatus,
  processingStatus: string | null,
): boolean {
  return commandBlocker(command, currentStatus, processingStatus) === null;
}

/** Whether *any* command is currently available — the difference between
 * "you may decide this document" and "this document is settled". */
export function hasAnyAvailableCommand(
  currentStatus: EvidenceStatus,
  processingStatus: string | null,
): boolean {
  return EVIDENCE_COMMANDS.some((command) =>
    isCommandAvailable(command, currentStatus, processingStatus),
  );
}
