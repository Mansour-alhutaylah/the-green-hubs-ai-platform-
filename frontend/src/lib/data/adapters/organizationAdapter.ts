import type { OrganizationResponse } from '@/lib/api/types';
import { isoTimestamp, type IsoTimestamp } from '../contracts/common';
import { organizationId } from '../contracts/ids';
import type { OrganizationSummary } from '../contracts/organization';

/** `created_at` is nullable on the wire and hand-authored in fixtures, so
 * the brand is applied only to a value that is actually present. */
function optionalTimestamp(value: string | null): IsoTimestamp | null {
  return value == null ? null : isoTimestamp(value);
}

/** The single wire → domain mapping for organizations. Live responses and
 * Preview fixtures both pass through here, which is what keeps a fixture
 * from drifting into a shape the API will never return. */
export function toOrganizationSummary(wire: OrganizationResponse): OrganizationSummary {
  return {
    id: organizationId(wire.id),
    name: wire.name,
    createdAt: optionalTimestamp(wire.created_at),
  };
}

export function toOrganizationSummaries(
  wire: readonly OrganizationResponse[],
): OrganizationSummary[] {
  return wire.map(toOrganizationSummary);
}
