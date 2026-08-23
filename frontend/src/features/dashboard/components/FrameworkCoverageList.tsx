import type { FrameworkCoverage } from '@/lib/data/contracts';
import { useLocale } from '@/lib/i18n/useLocale';

/**
 * Evidence coverage per reporting framework.
 *
 * The wording is the point. This is **evidence coverage**, meaning the
 * share of a framework's requested disclosures that have at least one
 * verified document attached in this synthetic workspace. It is not a
 * compliance score, not an assurance opinion, not a certification, and not
 * a statement that any disclosure would satisfy a regulator. The caption
 * says so directly rather than relying on a reader to infer it, because
 * "GRI 74%" beside a green bar invites exactly the wrong reading.
 *
 * Preview only. No endpoint maps documents to framework disclosures, so
 * Live has nothing to render and names the capability as unavailable.
 */
export function FrameworkCoverageList({
  frameworks,
}: {
  frameworks: readonly FrameworkCoverage[];
}) {
  const { t } = useLocale();

  if (frameworks.length === 0) {
    return (
      <p className="py-5 text-center text-meta text-gray-600">
        {t('dashboard.framework.empty')}
      </p>
    );
  }

  return (
    <>
      <ul className="flex flex-col gap-3.5">
        {frameworks.map((framework) => (
          <li key={framework.id} className="min-w-0">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
              <span className="text-meta font-bold text-forest-900">{framework.label}</span>
              <span className="text-caption text-gray-600">
                {t('dashboard.framework.covered', {
                  covered: framework.disclosuresCovered,
                  total: framework.disclosuresTotal,
                })}
              </span>
            </div>
            <div className="mt-1.5 flex items-center gap-2.5">
              <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-tint-100">
                <div
                  className="h-full rounded-full bg-forest-700"
                  style={{ width: `${framework.coveragePercent}%` }}
                  aria-hidden
                />
              </div>
              <span className="w-10 shrink-0 text-end text-meta font-bold text-forest-900" dir="ltr">
                {framework.coveragePercent}%
              </span>
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-4 text-caption text-gray-600">{t('dashboard.framework.disclaimer')}</p>
    </>
  );
}
