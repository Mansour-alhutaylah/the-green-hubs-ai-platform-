import type { EngagementResponse } from '@/lib/api/types';
import { isoTimestamp, type IsoTimestamp } from '../contracts/common';
import { engagementId, organizationId } from '../contracts/ids';
import type { EngagementSummary } from '../contracts/engagement';

function optionalTimestamp(value: string | null): IsoTimestamp | null {
  return value == null ? null : isoTimestamp(value);
}

/** The single wire → domain mapping for engagements.
 *
 * `organization_id` is carried through for *display* only — which
 * organization an engagement belongs to. It is never read back out of this
 * model and sent to a list endpoint as a scope argument; the backend
 * derives tenant scope from the bearer token. */
export function toEngagementSummary(wire: EngagementResponse): EngagementSummary {
  return {
    id: engagementId(wire.id),
    organizationId: wire.organization_id == null ? null : organizationId(wire.organization_id),
    title: wire.title,
    status: wire.status,
    createdAt: optionalTimestamp(wire.created_at),
  };
}

export function toEngagementSummaries(wire: readonly EngagementResponse[]): EngagementSummary[] {
  return wire.map(toEngagementSummary);
}
