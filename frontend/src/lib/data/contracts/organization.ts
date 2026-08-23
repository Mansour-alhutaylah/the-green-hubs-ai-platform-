import type { IsoTimestamp } from './common';
import type { OrganizationId } from './ids';

/**
 * Normalized Frontend view of an organization.
 *
 * Mirrors the verified backend contract `OrganizationResponse`
 * (`backend/app/schemas/organization.py`, route `GET /api/v1/organizations`)
 * and nothing more. The backend deliberately exposes three fields; this
 * model does not add a member count, a facility count, a sector, or a
 * status, because no endpoint returns any of them and inventing one would
 * put a fabricated figure on a Live screen.
 *
 * `createdAt` is nullable because the wire type is — some rows predate the
 * column being populated.
 */
export interface OrganizationSummary {
  readonly id: OrganizationId;
  readonly name: string;
  readonly createdAt: IsoTimestamp | null;
}
