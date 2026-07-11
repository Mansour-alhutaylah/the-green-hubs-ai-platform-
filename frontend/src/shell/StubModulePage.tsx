import { PageHeader } from './PageHeader';
import { ModulePendingNotice } from './ModulePendingNotice';

export interface StubModulePageProps {
  title: string;
  subtitle?: string;
}

/**
 * Phase 1 placeholder for an MVP route whose business logic (real tables,
 * charts, forms) ships in a later phase. Exists so routing, layout,
 * breadcrumbs, and RBAC gating are provable end to end right now — see
 * Appendix A for which tier reaches which route.
 */
export function StubModulePage({ title, subtitle }: StubModulePageProps) {
  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />
      <ModulePendingNotice />
    </div>
  );
}
