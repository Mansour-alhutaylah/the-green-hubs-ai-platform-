import type { Locale } from '@/lib/i18n/context';

/**
 * Fixture data only — just enough for the OrgSwitcher/RoleBadge chrome to
 * render something real in Phase 1. Real organization CRUD is a later
 * phase's business module.
 */
export interface MockOrganization {
  id: string;
  name: string;
  nameAr: string;
  sector: string;
}

export const DEMO_WORKSPACE_ORG_ID = 'org-green-hubs-demo';

export const MOCK_ORGANIZATIONS: MockOrganization[] = [
  {
    id: 'org-riyadh-industrial',
    name: 'Al-Riyadh Industrial Group',
    nameAr: 'مجموعة الرياض الصناعية',
    sector: 'Manufacturing',
  },
  {
    id: 'org-jeddah-logistics',
    name: 'Jeddah Logistics Co.',
    nameAr: 'شركة جدة للخدمات اللوجستية',
    sector: 'Logistics',
  },
  {
    id: 'org-neom-utilities',
    name: 'NEOM Utilities Authority',
    nameAr: 'هيئة مرافق نيوم',
    sector: 'Utilities',
  },
  {
    id: DEMO_WORKSPACE_ORG_ID,
    name: 'The Green Hubs Demo Workspace',
    nameAr: 'مساحة عمل ذا جرين هبز التجريبية',
    sector: 'Development preview',
  },
];

export function findOrganization(id: string): MockOrganization | undefined {
  return MOCK_ORGANIZATIONS.find((org) => org.id === id);
}

/** The one place an org's display name is picked per locale — both
 * OrgSwitcher (the trigger) and OrgSwitcherOverlay (the list) need it. */
export function localizedOrgName(org: MockOrganization, locale: Locale): string {
  return locale === 'ar' ? org.nameAr : org.name;
}
