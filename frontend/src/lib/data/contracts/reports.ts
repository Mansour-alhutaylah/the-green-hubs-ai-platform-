/**
 * The Preview-only reports contract.
 *
 * There is no reporting endpoint on this backend. That is the whole reason
 * this contract is Preview-only: Live has no source that could construct
 * one, so the Live Reports page renders a stated unavailable surface
 * instead of a list. No adapter maps a FastAPI response into these types,
 * and no `live/` module imports this file's fixtures.
 *
 * Nothing here asserts a regulatory outcome. A report has a *readiness*
 * percentage, describing how much of its evidence is attached and
 * verified in this synthetic workspace. It is never described as filed,
 * certified, assured, audited, or accepted by any authority.
 */

export type ReportStatus = 'draft' | 'inReview' | 'readyToPublish' | 'published';

export const REPORT_STATUSES: readonly ReportStatus[] = [
  'draft',
  'inReview',
  'readyToPublish',
  'published',
];

export type ReportFramework = 'gri' | 'csrd' | 'issb' | 'internal';

export const REPORT_FRAMEWORKS: readonly ReportFramework[] = [
  'gri',
  'csrd',
  'issb',
  'internal',
];

export interface ReportSection {
  readonly id: string;
  readonly title: string;
  /** Evidence documents attached to this section in the synthetic
   * workspace. */
  readonly evidenceCount: number;
  readonly complete: boolean;
}

export interface ReportSummary {
  readonly id: string;
  readonly name: string;
  readonly framework: ReportFramework;
  readonly status: ReportStatus;
  /** 0-100. Share of this report's sections that have verified evidence
   * attached. Not a compliance judgement. */
  readonly readinessPercent: number;
  readonly owner: string;
  readonly period: string;
  /** Authored ISO timestamp; Preview never reads the clock. */
  readonly updatedAt: string;
  readonly sections: readonly ReportSection[];
}

/** A starting point a reviewer could generate a report from. Templates are
 * descriptive only: choosing one in Preview creates nothing. */
export interface ReportTemplate {
  readonly id: string;
  readonly nameKey: string;
  readonly descriptionKey: string;
  readonly framework: ReportFramework;
  readonly sectionCount: number;
}

export interface ReportsWorkspace {
  readonly reportingPeriod: string;
  readonly reports: readonly ReportSummary[];
  readonly templates: readonly ReportTemplate[];
  /** Authored counts, not derived from `reports.length`. */
  readonly totals: {
    readonly all: number;
    readonly readyToPublish: number;
    readonly inReview: number;
    readonly averageReadinessPercent: number;
  };
}
