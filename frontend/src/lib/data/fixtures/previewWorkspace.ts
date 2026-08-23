import type {
  EngagementResponse,
  OrganizationResponse,
  UserProfileResponse,
} from '@/lib/api/types';
import { Role } from '@/features/rbac/roles';
import type { TeamMember } from '../contracts/team';
import { userId, organizationId } from '../contracts/ids';

/**
 * Deterministic Preview fixtures for the workspace pages (Organizations,
 * Engagements, Users & Roles).
 *
 * Same rules as the F1 dashboard fixtures: no `Math.random()`, no
 * `Date.now()`, literal ISO instants only, and every identity obviously
 * synthetic — no real company, government entity, customer, or person, and
 * no routable email domain (`.invalid` is reserved by RFC 2606).
 *
 * Organizations and engagements are authored in the **real wire shapes**
 * (`OrganizationResponse`, `EngagementResponse`) so they converge with Live
 * responses through the same adapters. A fixture that drifts from the
 * backend contract stops compiling.
 */

export const PREVIEW_ORGANIZATION_NAME = 'Green Hubs Demo Organization';

const PREVIEW_ORG_ID = 'preview-org-green-hubs-demo';

export const PREVIEW_ORGANIZATIONS: OrganizationResponse[] = [
  {
    id: PREVIEW_ORG_ID,
    name: PREVIEW_ORGANIZATION_NAME,
    created_at: '2026-01-12T08:00:00.000Z',
  },
];

export const PREVIEW_ENGAGEMENTS: EngagementResponse[] = [
  {
    id: 'preview-engagement-facility-alpha',
    organization_id: PREVIEW_ORG_ID,
    title: 'Facility Alpha — Annual Disclosure',
    status: 'active',
    created_at: '2026-02-02T09:30:00.000Z',
  },
  {
    id: 'preview-engagement-facility-beta',
    organization_id: PREVIEW_ORG_ID,
    title: 'Facility Beta — Water Stewardship Review',
    status: 'active',
    created_at: '2026-02-18T11:15:00.000Z',
  },
  {
    id: 'preview-engagement-supplier-programme',
    organization_id: PREVIEW_ORG_ID,
    title: 'Supplier Programme — Demo Set',
    status: 'draft',
    created_at: '2026-03-04T14:05:00.000Z',
  },
  {
    id: 'preview-engagement-prior-cycle',
    organization_id: PREVIEW_ORG_ID,
    title: 'Prior Reporting Cycle',
    status: 'closed',
    created_at: '2025-11-20T07:45:00.000Z',
  },
];

/** The signed-in Preview identity, in the real `auth/me` wire shape. */
export const PREVIEW_CURRENT_USER: UserProfileResponse = {
  id: 'preview-user-administrator',
  organization_id: PREVIEW_ORG_ID,
  full_name: 'Demo Administrator',
  email: 'demo.administrator@preview.invalid',
  role: Role.Admin,
};

/**
 * One member per canonical role, so the Preview team page can demonstrate
 * the full tier model. Authored directly in the domain shape (there is no
 * wire contract to converge with — the endpoint does not exist), and every
 * row is explicitly marked `preview-fixture`.
 */
export const PREVIEW_TEAM_MEMBERS: TeamMember[] = [
  {
    id: userId('preview-user-owner'),
    fullName: 'Demo Owner',
    email: 'demo.owner@preview.invalid',
    role: Role.Owner,
    organizationId: organizationId(PREVIEW_ORG_ID),
    source: 'preview-fixture',
    isCurrentUser: false,
  },
  {
    id: userId('preview-user-administrator'),
    fullName: 'Demo Administrator',
    email: 'demo.administrator@preview.invalid',
    role: Role.Admin,
    organizationId: organizationId(PREVIEW_ORG_ID),
    source: 'preview-fixture',
    isCurrentUser: true,
  },
  {
    id: userId('preview-user-approver'),
    fullName: 'Reviewer A',
    email: 'reviewer.a@preview.invalid',
    role: Role.Approver,
    organizationId: organizationId(PREVIEW_ORG_ID),
    source: 'preview-fixture',
    isCurrentUser: false,
  },
  {
    id: userId('preview-user-editor'),
    fullName: 'Editor A',
    email: 'editor.a@preview.invalid',
    role: Role.Editor,
    organizationId: organizationId(PREVIEW_ORG_ID),
    source: 'preview-fixture',
    isCurrentUser: false,
  },
  {
    id: userId('preview-user-viewer'),
    fullName: 'Viewer A',
    email: 'viewer.a@preview.invalid',
    role: Role.Viewer,
    organizationId: organizationId(PREVIEW_ORG_ID),
    source: 'preview-fixture',
    isCurrentUser: false,
  },
];
