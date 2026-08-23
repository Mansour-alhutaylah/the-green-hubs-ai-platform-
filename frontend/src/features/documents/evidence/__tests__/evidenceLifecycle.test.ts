import { describe, expect, it } from 'vitest';
import type { EvidenceStatus } from '@/lib/api/types';
import {
  EVIDENCE_COMMANDS,
  EvidenceCommand,
  commandBlocker,
  hasAnyAvailableCommand,
  isCommandAvailable,
  isRetrievalEligible,
  requiresReason,
  acceptsSuccessor,
  targetStatusFor,
} from '../evidenceLifecycle';

/**
 * The frontend transcription of the evidence state machine.
 *
 * Every rule here is also enforced by the backend, inside the transition's
 * own SQL predicate. What these tests protect is the transcription: a
 * table that quietly widened would offer a reviewer a control the server
 * then refuses with 409, and a table that quietly narrowed would hide a
 * decision an authorized reviewer is entitled to make.
 *
 * The states are deliberately exercised as a matrix rather than as a
 * sequence — treating them as a pipeline is the specific misreading the
 * backend module warns against.
 */

const ALL_STATUSES: readonly EvidenceStatus[] = [
  'PENDING_REVIEW',
  'VERIFIED',
  'REJECTED',
  'RESTRICTED',
  'SUPERSEDED',
];

const DECIDED_STATUSES: readonly EvidenceStatus[] = ['REJECTED', 'RESTRICTED', 'SUPERSEDED'];

describe('Evidence retrieval eligibility', () => {
  it('treats VERIFIED as the only retrieval-eligible state', () => {
    expect(isRetrievalEligible('VERIFIED')).toBe(true);
    for (const status of ALL_STATUSES.filter((s) => s !== 'VERIFIED')) {
      expect(isRetrievalEligible(status)).toBe(false);
    }
  });

  it('treats the initial state as ineligible, so retrieval fails closed', () => {
    expect(isRetrievalEligible('PENDING_REVIEW')).toBe(false);
  });
});

describe('Evidence transition matrix', () => {
  it('allows every command from the initial state on a processed document', () => {
    for (const command of EVIDENCE_COMMANDS) {
      expect(isCommandAvailable(command, 'PENDING_REVIEW', 'PROCESSED')).toBe(true);
    }
  });

  it('allows a verified document to be withdrawn, but never re-verified', () => {
    expect(commandBlocker(EvidenceCommand.Verify, 'VERIFIED', 'PROCESSED')).toBe(
      'already-in-state',
    );
    for (const command of [
      EvidenceCommand.Reject,
      EvidenceCommand.Restrict,
      EvidenceCommand.Supersede,
    ]) {
      expect(isCommandAvailable(command, 'VERIFIED', 'PROCESSED')).toBe(true);
    }
  });

  it.each(DECIDED_STATUSES)('treats %s as terminal for every command', (status) => {
    for (const command of EVIDENCE_COMMANDS) {
      expect(isCommandAvailable(command, status, 'PROCESSED')).toBe(false);
    }
    expect(hasAnyAvailableCommand(status, 'PROCESSED')).toBe(false);
  });

  it('reports a repeat of the current decision distinctly from a refusal', () => {
    // "You already did this" and "this cannot be re-decided" are different
    // things to tell a reviewer.
    expect(commandBlocker(EvidenceCommand.Reject, 'REJECTED', 'PROCESSED')).toBe(
      'already-in-state',
    );
    expect(commandBlocker(EvidenceCommand.Verify, 'REJECTED', 'PROCESSED')).toBe(
      'decision-recorded',
    );
  });
});

describe('The processing precondition', () => {
  it.each(['PENDING', 'PROCESSING', 'FAILED', null])(
    'refuses verify while processing_status is %s',
    (processingStatus) => {
      expect(commandBlocker(EvidenceCommand.Verify, 'PENDING_REVIEW', processingStatus)).toBe(
        'not-processed',
      );
    },
  );

  it('constrains approval only — never withdrawal', () => {
    // A document whose extraction FAILED is exactly the kind that needs
    // rejecting; a precondition there would strand it forever.
    for (const command of [
      EvidenceCommand.Reject,
      EvidenceCommand.Restrict,
      EvidenceCommand.Supersede,
    ]) {
      expect(isCommandAvailable(command, 'PENDING_REVIEW', 'FAILED')).toBe(true);
    }
  });

  it('leaves a document decidable even when it cannot be approved', () => {
    expect(hasAnyAvailableCommand('PENDING_REVIEW', 'FAILED')).toBe(true);
  });
});

describe('Command requirements', () => {
  it('requires a reason for every withdrawal, and none for approval', () => {
    expect(requiresReason(EvidenceCommand.Verify)).toBe(false);
    for (const command of [
      EvidenceCommand.Reject,
      EvidenceCommand.Restrict,
      EvidenceCommand.Supersede,
    ]) {
      expect(requiresReason(command)).toBe(true);
    }
  });

  it('accepts a successor on supersede alone', () => {
    expect(acceptsSuccessor(EvidenceCommand.Supersede)).toBe(true);
    for (const command of [
      EvidenceCommand.Verify,
      EvidenceCommand.Reject,
      EvidenceCommand.Restrict,
    ]) {
      expect(acceptsSuccessor(command)).toBe(false);
    }
  });

  it('maps each command to a distinct recorded state', () => {
    const targets = EVIDENCE_COMMANDS.map(targetStatusFor);
    expect(new Set(targets).size).toBe(EVIDENCE_COMMANDS.length);
    expect(targets).not.toContain('PENDING_REVIEW');
  });
});
