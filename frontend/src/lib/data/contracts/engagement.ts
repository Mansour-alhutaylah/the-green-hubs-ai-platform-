import type { IsoTimestamp } from './common';
import type { EngagementId, OrganizationId } from './ids';

/**
 * Normalized Frontend view of an engagement.
 *
 * Mirrors `EngagementResponse` (`GET /api/v1/engagements`). `status` is a
 * nullable free-form `str` on the wire, not a database enum, so this
 * model keeps it as an open string and the UI maps *recognized* values to
 * a badge tone while rendering anything else verbatim. Closing the union
 * here would make an unrecognized backend value unrenderable.
 */
export type RecognizedEngagementStatus = 'active' | 'draft' | 'closed' | 'archived';

export const RECOGNIZED_ENGAGEMENT_STATUSES: readonly RecognizedEngagementStatus[] = [
  'active',
  'draft',
  'closed',
  'archived',
];

export interface EngagementSummary {
  readonly id: EngagementId;
  /** Nullable on the wire; the backend scopes by the caller's token, so
   * this is display context only and is never sent back as an authority. */
  readonly organizationId: OrganizationId | null;
  readonly title: string;
  readonly status: string | null;
  readonly createdAt: IsoTimestamp | null;
}

/** Normalizes a stored status for tone lookup without discarding the
 * original value. Returns `null` for anything the UI has not been taught. */
export function recognizeEngagementStatus(status: string | null): RecognizedEngagementStatus | null {
  if (status == null) return null;
  const normalized = status.trim().toLowerCase();
  return (
    RECOGNIZED_ENGAGEMENT_STATUSES.find((candidate) => candidate === normalized) ?? null
  );
}
