import type { ReportsWorkspace } from '../contracts/reports';

/**
 * Deterministic Preview fixtures for the Reports workspace.
 *
 * Literal values only, no `Math.random()`, no `Date.now()`. Owners are the
 * same synthetic people as `previewWorkspace.ts`, so a reviewer moving
 * between Users and Reports sees one consistent cast rather than two.
 *
 * Never imported by a Live source. There is no reporting endpoint at all,
 * so Live has nothing to render and says so.
 *
 * `readinessPercent` describes evidence attachment within this synthetic
 * workspace. Nothing here is described as filed, certified, assured, or
 * accepted by any authority, because none of that would be true.
 */
export const PREVIEW_REPORTS: ReportsWorkspace = {
  reportingPeriod: 'FY 2025',

  totals: {
    // Authored, not `reports.length`. The same discipline the Live
    // dashboard is held to.
    all: 6,
    readyToPublish: 2,
    inReview: 2,
    averageReadinessPercent: 63,
  },

  reports: [
    {
      id: 'rep-gri-annual-2025',
      name: 'GRI Sustainability Statement 2025',
      framework: 'gri',
      status: 'readyToPublish',
      readinessPercent: 92,
      owner: 'Layla Demirci',
      period: 'FY 2025',
      updatedAt: '2026-03-28T14:20:00.000Z',
      sections: [
        { id: 's1', title: 'Organizational profile', evidenceCount: 9, complete: true },
        { id: 's2', title: 'Energy and emissions', evidenceCount: 14, complete: true },
        { id: 's3', title: 'Water and effluents', evidenceCount: 6, complete: true },
        { id: 's4', title: 'Workforce and safety', evidenceCount: 4, complete: false },
      ],
    },
    {
      id: 'rep-csrd-esrs-e1',
      name: 'CSRD ESRS E1 Climate Disclosure',
      framework: 'csrd',
      status: 'inReview',
      readinessPercent: 58,
      owner: 'Noor Haddad',
      period: 'FY 2025',
      updatedAt: '2026-03-25T11:05:00.000Z',
      sections: [
        { id: 's1', title: 'Transition plan', evidenceCount: 5, complete: true },
        { id: 's2', title: 'Scope 1 and 2 emissions', evidenceCount: 11, complete: true },
        { id: 's3', title: 'Scope 3 emissions', evidenceCount: 2, complete: false },
        { id: 's4', title: 'Targets and progress', evidenceCount: 0, complete: false },
      ],
    },
    {
      id: 'rep-issb-s2',
      name: 'ISSB S2 Climate-related Disclosures',
      framework: 'issb',
      status: 'inReview',
      readinessPercent: 61,
      owner: 'Tomas Iversen',
      period: 'FY 2025',
      updatedAt: '2026-03-22T08:40:00.000Z',
      sections: [
        { id: 's1', title: 'Governance', evidenceCount: 7, complete: true },
        { id: 's2', title: 'Strategy and resilience', evidenceCount: 4, complete: true },
        { id: 's3', title: 'Risk management', evidenceCount: 3, complete: false },
      ],
    },
    {
      id: 'rep-facility-alpha-q4',
      name: 'Facility Alpha Quarterly Review',
      framework: 'internal',
      status: 'readyToPublish',
      readinessPercent: 88,
      owner: 'Layla Demirci',
      period: 'Q4 2025',
      updatedAt: '2026-03-19T16:10:00.000Z',
      sections: [
        { id: 's1', title: 'Site energy summary', evidenceCount: 8, complete: true },
        { id: 's2', title: 'Waste streams', evidenceCount: 5, complete: true },
      ],
    },
    {
      id: 'rep-gri-supplier',
      name: 'Supplier Assessment Appendix',
      framework: 'gri',
      status: 'draft',
      readinessPercent: 24,
      owner: 'Noor Haddad',
      period: 'FY 2025',
      updatedAt: '2026-03-11T09:55:00.000Z',
      sections: [
        { id: 's1', title: 'Supplier register', evidenceCount: 3, complete: false },
        { id: 's2', title: 'Screening outcomes', evidenceCount: 0, complete: false },
      ],
    },
    {
      id: 'rep-board-summary-2024',
      name: 'Board Sustainability Summary 2024',
      framework: 'internal',
      status: 'published',
      readinessPercent: 100,
      owner: 'Tomas Iversen',
      period: 'FY 2024',
      updatedAt: '2025-11-04T13:30:00.000Z',
      sections: [
        { id: 's1', title: 'Year in review', evidenceCount: 12, complete: true },
        { id: 's2', title: 'Targets and outcomes', evidenceCount: 9, complete: true },
      ],
    },
  ],

  templates: [
    {
      id: 'tpl-gri-core',
      nameKey: 'reports.template.gri.name',
      descriptionKey: 'reports.template.gri.description',
      framework: 'gri',
      sectionCount: 12,
    },
    {
      id: 'tpl-csrd-esrs',
      nameKey: 'reports.template.csrd.name',
      descriptionKey: 'reports.template.csrd.description',
      framework: 'csrd',
      sectionCount: 18,
    },
    {
      id: 'tpl-issb-s2',
      nameKey: 'reports.template.issb.name',
      descriptionKey: 'reports.template.issb.description',
      framework: 'issb',
      sectionCount: 9,
    },
    {
      id: 'tpl-internal-quarterly',
      nameKey: 'reports.template.internal.name',
      descriptionKey: 'reports.template.internal.description',
      framework: 'internal',
      sectionCount: 5,
    },
  ],
};

/** The `partial` scenario: one draft started, nothing reviewed. */
export const PREVIEW_REPORTS_PARTIAL: ReportsWorkspace = {
  reportingPeriod: 'FY 2025',
  totals: { all: 1, readyToPublish: 0, inReview: 0, averageReadinessPercent: 12 },
  reports: [
    {
      id: 'rep-gri-annual-2025',
      name: 'GRI Sustainability Statement 2025',
      framework: 'gri',
      status: 'draft',
      readinessPercent: 12,
      owner: 'Layla Demirci',
      period: 'FY 2025',
      updatedAt: '2026-03-28T14:20:00.000Z',
      sections: [
        { id: 's1', title: 'Organizational profile', evidenceCount: 2, complete: false },
      ],
    },
  ],
  templates: PREVIEW_REPORTS.templates,
};
