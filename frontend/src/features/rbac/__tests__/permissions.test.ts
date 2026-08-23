import { describe, expect, it } from 'vitest';
import { Role } from '../roles';
import { Permission, evidenceReviewRoles, hasPermission } from '../permissions';

/**
 * The frontend mirror of the **M-4** evidence-review policy.
 *
 * This decides what is *offered*, not what is *allowed* — the backend
 * re-derives the role server-side and refuses an unauthorized command with
 * 403 whatever this says. `backend/tests/domain/security/test_permissions.py`
 * reads `permissions.ts` and fails if the two policies ever disagree, so
 * this file pins the frontend half and that guard pins them together.
 */

/** The recorded matrix, written out once and read by every case below. */
const M4_MATRIX: ReadonlyArray<readonly [Role, boolean]> = [
  [Role.Viewer, false],
  [Role.Editor, false],
  [Role.Approver, true],
  [Role.Admin, true],
  [Role.Owner, true],
];

describe('Evidence review permission policy', () => {
  it('covers every role in the vocabulary', () => {
    expect(M4_MATRIX.map(([role]) => role).sort()).toEqual([...Object.values(Role)].sort());
  });

  it.each(M4_MATRIX)('resolves %s to the recorded M-4 answer', (role, allowed) => {
    expect(hasPermission(role, Permission.EvidenceReview)).toBe(allowed);
  });

  it('denies an editor specifically, which is the substance of M-4', () => {
    // Producing evidence and approving it are separate duties; an editor
    // who could approve their own upload would make review decorative.
    expect(hasPermission(Role.Editor, Permission.EvidenceReview)).toBe(false);
    expect(hasPermission(Role.Approver, Permission.EvidenceReview)).toBe(true);
  });

  it('fails closed on a missing role', () => {
    expect(hasPermission(null, Permission.EvidenceReview)).toBe(false);
    expect(hasPermission(undefined, Permission.EvidenceReview)).toBe(false);
  });

  it('fails closed on a role outside the closed vocabulary', () => {
    for (const unknown of ['reviewer', 'superuser', 'EDITOR', '', '   ']) {
      expect(hasPermission(unknown as Role, Permission.EvidenceReview)).toBe(false);
    }
  });

  it('exposes exactly the approving roles', () => {
    expect([...evidenceReviewRoles()]).toEqual([Role.Approver, Role.Admin, Role.Owner]);
  });

  it('is deterministic', () => {
    const first = M4_MATRIX.map(([role]) => hasPermission(role, Permission.EvidenceReview));
    const second = M4_MATRIX.map(([role]) => hasPermission(role, Permission.EvidenceReview));
    expect(first).toEqual(second);
  });
});
