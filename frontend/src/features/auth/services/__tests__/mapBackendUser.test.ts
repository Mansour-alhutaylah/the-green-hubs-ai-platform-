import { describe, expect, it } from 'vitest';
import { Role } from '@/features/rbac/roles';
import { mapBackendRole, mapBackendUser } from '../mapBackendUser';

describe('mapBackendRole', () => {
  it.each([
    ['owner', Role.Owner],
    ['ADMIN', Role.Admin],
    [' approver ', Role.Approver],
    ['editor', Role.Editor],
    ['viewer', Role.Viewer],
  ])('maps backend role %s to %s', (role, expected) => {
    expect(mapBackendRole(role)).toBe(expected);
  });

  it('defaults an unrecognized role to Viewer, the least-privileged tier', () => {
    expect(mapBackendRole('super-admin')).toBe(Role.Viewer);
  });

  it('defaults a null role to Viewer', () => {
    expect(mapBackendRole(null)).toBe(Role.Viewer);
  });
});

describe('mapBackendUser', () => {
  it('maps a profile with an organization to a single-item orgIds array', () => {
    const user = mapBackendUser({
      id: 'user-1',
      organization_id: 'org-1',
      full_name: 'Reem Al-Harbi',
      email: 'reem@example.com',
      role: 'admin',
    });

    expect(user).toEqual({
      id: 'user-1',
      name: 'Reem Al-Harbi',
      email: 'reem@example.com',
      role: Role.Admin,
      orgIds: ['org-1'],
    });
  });

  it('maps a profile with no organization to an empty orgIds array', () => {
    const user = mapBackendUser({
      id: 'user-2',
      organization_id: null,
      full_name: 'Faisal Al-Dossary',
      email: 'faisal@example.com',
      role: null,
    });

    expect(user.orgIds).toEqual([]);
    expect(user.role).toBe(Role.Viewer);
  });
});
