import { useState, type ReactNode } from 'react';
import { Badge, Button, Icon, SectionCard, Select } from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { useWorkspace } from '@/features/organizations/workspace/WorkspaceContext';
import { ROLE_LABELS } from '@/features/rbac/roles';
import { DetailList } from '@/features/workspace/components/DetailList';
import { useApplicationInfo, useIntegrationCapabilities } from '@/lib/data/hooks/useApplicationInfo';
import type { IntegrationCapability } from '@/lib/data/contracts';
import { isPreviewMode } from '@/lib/data/source';
import { AVAILABLE_LOCALES, hasSelectableLocales } from '@/lib/i18n/availability';
import type { Locale } from '@/lib/i18n/context';
import type { StringKey } from '@/lib/i18n/strings/en';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';

/**
 * Settings. Admin+ route (the router's `RoleGuard` covers it).
 *
 * **What changed and why.** This page used to render all six sections
 * stacked as full-width cards, so a reviewer scrolled through roughly two
 * and a half screens of prose to reach About, and every section competed
 * for attention equally. It read as documentation rather than as settings.
 *
 * It is now a settings *workspace*: a section list beside one active
 * panel, which is the shape every mature product settles on for the same
 * reason. Only one section renders at a time, so the page is a single
 * screenful at every width, and Overview answers the common case (what is
 * my account, what mode am I in, what is switched on) without opening
 * anything.
 *
 * The section list is a rail from `lg` up and a `<select>` below it, not a
 * horizontal scroll strip. A strip hides its own overflow on a phone,
 * which is how a settings section becomes unreachable.
 *
 * **The truthfulness rules are unchanged**, and they are the reason this
 * page exists in the form it does:
 *
 * > A Settings screen is visible to any signed-in user who can reach the
 * > route. Nothing on it may be an infrastructure identifier.
 *
 * So no section renders a database host, a Supabase project URL or
 * reference, a DSN, a bucket, an API origin, a region, an account or
 * service identifier, a key name, or any credential. Configuration
 * presence is reported as a boolean and never as a value, which is
 * structural rather than careful: `ApplicationInfo` has no field for any
 * of them.
 *
 * Data residency has no product API, so it states that rather than naming
 * a region it cannot verify. Multi-factor authentication is stated as not
 * implemented, and the mock verification-code flow a previous audit
 * removed is not restored. n8n is neither contacted nor listed.
 */

const SECTIONS = [
  'overview',
  'account',
  'workspace',
  'language',
  'security',
  'residency',
  'integrations',
  'about',
] as const;

type SectionId = (typeof SECTIONS)[number];

const SECTION_LABEL_KEY: Record<SectionId, StringKey> = {
  overview: 'settings.section.overview',
  account: 'settings.section.account',
  workspace: 'settings.section.workspace',
  language: 'settings.section.language',
  security: 'settings.section.security',
  residency: 'settings.section.residency',
  integrations: 'settings.section.integrations',
  about: 'settings.section.about',
};

const INTEGRATION_LABEL_KEY: Record<IntegrationCapability['id'], StringKey> = {
  documentStorage: 'settings.integrations.documentStorage',
  documentAnalysis: 'settings.integrations.documentAnalysis',
  authentication: 'settings.integrations.authentication',
};

export function SettingsPage() {
  const { t } = useLocale();
  const [active, setActive] = useState<SectionId>('overview');

  return (
    <div>
      <PageHeader
        eyebrow={t('settings.eyebrow')}
        title={t('nav.settings')}
        subtitle={t('settings.subtitle')}
      />

      <div className="flex flex-col gap-4 lg:flex-row lg:gap-6">
        {/* Below `lg` the section list is a real `<select>`. A horizontal
            strip would hide its own overflow on a phone, which is how a
            settings section becomes unreachable. */}
        <div className="lg:hidden">
          {/* A distinct accessible name from the rail's `aria-label`: both
              controls exist in the DOM at every width, and two elements
              sharing one name is ambiguous to a screen reader and to any
              query that looks one up. */}
          <label
            htmlFor="settings-section"
            className="mb-1.5 block text-meta font-bold text-ink-900"
          >
            {t('settings.nav.select')}
          </label>
          <Select
            id="settings-section"
            controlSize="md"
            value={active}
            onChange={(event) => setActive(event.target.value as SectionId)}
            options={SECTIONS.map((section) => ({
              value: section,
              label: t(SECTION_LABEL_KEY[section]),
            }))}
          />
        </div>

        <nav aria-label={t('settings.nav.label')} className="hidden lg:block lg:w-56 lg:shrink-0">
          <ul className="flex flex-col gap-0.5">
            {SECTIONS.map((section) => {
              const selected = section === active;
              return (
                <li key={section}>
                  <button
                    type="button"
                    aria-current={selected ? 'page' : undefined}
                    onClick={() => setActive(section)}
                    className={
                      selected
                        ? 'flex w-full items-center rounded-s bg-tint-100 px-3 py-2 text-start text-body font-bold text-forest-900'
                        : 'flex w-full items-center rounded-s px-3 py-2 text-start text-body text-gray-600 transition-colors hover:bg-tint-100 hover:text-forest-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700'
                    }
                  >
                    {t(SECTION_LABEL_KEY[section])}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="min-w-0 flex-1">
          <ActiveSection id={active} onNavigate={setActive} />
        </div>
      </div>
    </div>
  );
}

function ActiveSection({
  id,
  onNavigate,
}: {
  id: SectionId;
  onNavigate: (section: SectionId) => void;
}) {
  switch (id) {
    case 'overview':
      return <OverviewSection onNavigate={onNavigate} />;
    case 'account':
      return <AccountSection />;
    case 'workspace':
      return <WorkspaceSection />;
    case 'language':
      return <LanguageSection />;
    case 'security':
      return <SecuritySection />;
    case 'residency':
      return <ResidencySection />;
    case 'integrations':
      return <IntegrationsSection />;
    case 'about':
      return <AboutSection />;
  }
}

/** A compact status row. One fact per line, with the status carried as
 * text so it survives greyscale and screen readers alike. */
function StatusRow({
  label,
  value,
  tone = 'neutral',
  onOpen,
  openLabel,
}: {
  label: string;
  value: ReactNode;
  tone?: 'neutral' | 'muted';
  onOpen?: () => void;
  openLabel?: string;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2.5">
      <span className="text-meta font-semibold text-ink-900">{label}</span>
      <span className="flex items-center gap-3">
        <span
          className={
            tone === 'muted' ? 'text-meta text-gray-600' : 'text-meta font-bold text-forest-900'
          }
        >
          {value}
        </span>
        {onOpen && openLabel && (
          <button
            type="button"
            onClick={onOpen}
            className="rounded-s text-caption font-semibold text-leaf-700 underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
          >
            {openLabel}
          </button>
        )}
      </span>
    </div>
  );
}

/**
 * Overview answers the questions people actually open Settings to check,
 * without making them open anything: who am I, where am I, which mode is
 * this, what language, and which capabilities are switched on. Each row
 * links to the section that owns the detail.
 */
function OverviewSection({ onNavigate }: { onNavigate: (section: SectionId) => void }) {
  const { t } = useLocale();
  const { user } = useAuth();
  const workspace = useWorkspace();
  const info = useApplicationInfo(t('brand.name'));

  const open = t('settings.overview.open');

  return (
    <SectionCard
      title={t('settings.overview.title')}
      description={t('settings.overview.description')}
      contentClassName="p-0 sm:p-0"
    >
      <div className="divide-y divide-line-200 px-4 sm:px-5">
        <StatusRow
          label={t('settings.general.field.name')}
          value={<span data-user-content>{user?.name ?? t('workspace.value.notRecorded')}</span>}
          onOpen={() => onNavigate('account')}
          openLabel={open}
        />
        <StatusRow
          label={t('settings.general.field.role')}
          value={user ? ROLE_LABELS[user.role] : t('workspace.value.notRecorded')}
          onOpen={() => onNavigate('account')}
          openLabel={open}
        />
        <StatusRow
          label={t('settings.general.field.organization')}
          value={
            <span data-user-content>
              {workspace.organization?.name ?? t('settings.general.organization.missing')}
            </span>
          }
          onOpen={() => onNavigate('workspace')}
          openLabel={open}
        />
        <StatusRow
          label={t('settings.general.mode.title')}
          value={
            info.mode === 'preview'
              ? t('settings.general.mode.preview')
              : t('settings.general.mode.live')
          }
          onOpen={() => onNavigate('about')}
          openLabel={open}
        />
        <StatusRow
          label={t('settings.language.current')}
          value={t('settings.language.english')}
          onOpen={() => onNavigate('language')}
          openLabel={open}
        />
        <StatusRow
          label={t('settings.security.mfa.title')}
          value={t('settings.overview.notImplemented')}
          tone="muted"
          onOpen={() => onNavigate('security')}
          openLabel={open}
        />
        <StatusRow
          label={t('settings.section.residency')}
          value={t('settings.overview.notReported')}
          tone="muted"
          onOpen={() => onNavigate('residency')}
          openLabel={open}
        />
        <StatusRow
          label={t('settings.section.integrations')}
          value={t('settings.integrations.state.notConfigurable')}
          tone="muted"
          onOpen={() => onNavigate('integrations')}
          openLabel={open}
        />
      </div>
    </SectionCard>
  );
}

/** Real identity, server-resolved. */
function AccountSection() {
  const { t } = useLocale();
  const { user, sessionKind } = useAuth();
  const info = useApplicationInfo(t('brand.name'));

  return (
    <SectionCard
      title={t('settings.general.identity.title')}
      description={t('settings.general.identity.description')}
    >
      <DetailList
        items={[
          {
            id: 'name',
            label: t('settings.general.field.name'),
            value: <span data-user-content>{user?.name ?? t('workspace.value.notRecorded')}</span>,
          },
          {
            id: 'email',
            label: t('settings.general.field.email'),
            value: (
              <span dir="ltr" className="break-all" data-user-content>
                {user?.email ?? t('workspace.value.notRecorded')}
              </span>
            ),
          },
          {
            id: 'role',
            label: t('settings.general.field.role'),
            value: user ? ROLE_LABELS[user.role] : t('workspace.value.notRecorded'),
          },
          {
            id: 'mode',
            label: t('settings.general.mode.title'),
            value: (
              <>
                <Badge
                  className={
                    info.mode === 'preview'
                      ? 'border-leaf-300 bg-leaf-100 text-leaf-700'
                      : 'border-line-200'
                  }
                >
                  {info.mode === 'preview'
                    ? t('settings.general.mode.preview')
                    : t('settings.general.mode.live')}
                </Badge>
                <span className="mt-1 block text-caption text-gray-600">
                  {info.mode === 'preview'
                    ? t('settings.general.mode.preview.description')
                    : t('settings.general.mode.live.description')}
                </span>
                {sessionKind === 'preview' && (
                  <span className="mt-1 block text-caption text-gray-600">
                    {t('settings.security.session.method.preview')}
                  </span>
                )}
              </>
            ),
          },
        ]}
      />
    </SectionCard>
  );
}

/**
 * Workspace context, plus the one genuinely local Preview control on this
 * page.
 *
 * The default reporting period is a real `useState` and nothing else. It
 * issues no request, writes to no storage, and is gone on reload, and the
 * notice says exactly that rather than implying a save. In Live the
 * control is absent entirely: there is no preferences endpoint, so a
 * control that appeared to persist a choice would be the clearest possible
 * lie on this page.
 */
function WorkspaceSection() {
  const { t } = useLocale();
  const workspace = useWorkspace();
  const preview = isPreviewMode();

  const [period, setPeriod] = useState('FY 2025');
  const [touched, setTouched] = useState(false);

  return (
    <SectionCard
      title={t('settings.workspace.title')}
      description={t('settings.workspace.description')}
    >
      <DetailList
        items={[
          {
            id: 'organization',
            label: t('settings.general.field.organization'),
            value: (
              <span data-user-content>
                {workspace.organization?.name ?? t('settings.general.organization.missing')}
              </span>
            ),
          },
        ]}
      />

      {preview ? (
        <div className="mt-6 border-t border-line-200 pt-5">
          <label
            htmlFor="settings-period"
            className="mb-1.5 block text-meta font-bold text-ink-900"
          >
            {t('settings.workspace.period.label')}
          </label>
          <div className="flex max-w-sm flex-col gap-2">
            <Select
              id="settings-period"
              controlSize="md"
              value={period}
              onChange={(event) => {
                setPeriod(event.target.value);
                setTouched(true);
              }}
              aria-describedby="settings-period-note"
              options={[
                { value: 'FY 2025', label: 'FY 2025' },
                { value: 'FY 2024', label: 'FY 2024' },
                { value: 'Q4 2025', label: 'Q4 2025' },
              ]}
            />
            <p id="settings-period-note" className="text-caption text-gray-600">
              {t('settings.workspace.period.hint')}
            </p>
          </div>

          {touched && (
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <output className="rounded-m border border-dashed border-line-300 bg-tint-100 px-3 py-2 text-caption font-semibold text-gray-600">
                {t('settings.demoOnly')}
              </output>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setPeriod('FY 2025');
                  setTouched(false);
                }}
              >
                {t('settings.workspace.period.reset')}
              </Button>
            </div>
          )}
        </div>
      ) : (
        <p className="mt-6 border-t border-line-200 pt-5 text-body text-gray-600">
          {t('settings.workspace.preferences.unavailable')}
        </p>
      )}
    </SectionCard>
  );
}

function LanguageSection() {
  const { t, locale, setLocale } = useLocale();
  const selectable = hasSelectableLocales();

  return (
    <SectionCard
      title={t('settings.language.title')}
      description={t('settings.language.description')}
    >
      {selectable ? (
        <div className="flex max-w-sm flex-col gap-1.5">
          <label htmlFor="settings-language" className="text-meta font-bold text-ink-900">
            {t('settings.language.label')}
          </label>
          <Select
            id="settings-language"
            controlSize="md"
            value={locale}
            // `setLocale` resolves through the availability gate, so an
            // unavailable value cannot be activated from here either.
            onChange={(event) => setLocale(event.target.value as Locale)}
            aria-describedby="settings-language-note"
            options={AVAILABLE_LOCALES.map((available) => ({
              value: available,
              label:
                available === 'ar' ? t('settings.language.arabic') : t('settings.language.english'),
            }))}
          />
          <p id="settings-language-note" className="text-caption text-gray-600">
            {t('settings.language.note')}
          </p>
        </div>
      ) : (
        <>
          <DetailList
            items={[
              {
                id: 'current',
                label: t('settings.language.current'),
                value: t('settings.language.english'),
              },
            ]}
          />
          <p className="mt-4 max-w-3xl text-meta text-gray-600">
            {t('settings.language.onlyOption')}
          </p>
          <div className="mt-5 rounded-m border border-dashed border-line-300 bg-tint-100 px-4 py-3">
            <p className="text-meta font-bold text-ink-900">
              {t('settings.language.future.title')}
            </p>
            <p className="mt-1 max-w-3xl text-caption text-gray-600">
              {t('settings.language.future.description')}
            </p>
          </div>
        </>
      )}
    </SectionCard>
  );
}

function SecuritySection() {
  const { t } = useLocale();
  const { user, sessionKind, logout } = useAuth();

  return (
    <SectionCard title={t('settings.security.title')}>
      <DetailList
        items={[
          {
            id: 'signed-in-as',
            label: t('settings.security.session.signedInAs'),
            value: (
              <span dir="ltr" className="break-all" data-user-content>
                {user?.email ?? t('workspace.value.notRecorded')}
              </span>
            ),
          },
          {
            id: 'method',
            label: t('settings.security.session.method'),
            value:
              sessionKind === 'preview'
                ? t('settings.security.session.method.preview')
                : t('settings.security.session.method.password'),
          },
          {
            id: 'expiry',
            label: t('settings.security.session.title'),
            value: t('settings.security.session.expiry'),
          },
        ]}
      />

      <div className="mt-6 border-t border-line-200 pt-5">
        <p className="text-body font-bold text-ink-900">{t('settings.security.mfa.title')}</p>
        <p className="mt-2 max-w-3xl text-body text-gray-600">
          {t('settings.security.mfa.description')}
        </p>
      </div>

      <div className="mt-6">
        <Button variant="ghost" onClick={() => void logout()}>
          <Icon name="log-out" size={16} />
          {t('settings.security.signOut')}
        </Button>
      </div>
    </SectionCard>
  );
}

function ResidencySection() {
  const { t } = useLocale();
  return (
    <SectionCard className="border-dashed" title={t('settings.residency.title')}>
      <p className="text-body font-bold text-ink-900">
        {t('settings.residency.unavailable.title')}
      </p>
      <p className="mt-2 max-w-3xl text-body text-gray-600">
        {t('settings.residency.unavailable.description')}
      </p>
    </SectionCard>
  );
}

function IntegrationsSection() {
  const { t } = useLocale();
  const capabilities = useIntegrationCapabilities();

  return (
    <SectionCard
      title={t('settings.integrations.title')}
      description={t('settings.integrations.description')}
    >
      <ul className="flex flex-col gap-2.5">
        {capabilities.map((capability) => (
          <li
            key={capability.id}
            className="flex flex-col gap-2 rounded-m border border-line-200 px-4 py-3 min-[30rem]:flex-row min-[30rem]:items-center min-[30rem]:justify-between"
          >
            <span className="text-body font-bold text-ink-900">
              {t(INTEGRATION_LABEL_KEY[capability.id])}
            </span>
            <Badge className="self-start min-[30rem]:self-auto">
              {t('settings.integrations.state.notConfigurable')}
            </Badge>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}

function AboutSection() {
  const { t } = useLocale();
  const info = useApplicationInfo(t('brand.name'));

  const configured = (value: boolean) =>
    value ? t('settings.about.configured') : t('settings.about.notConfigured');

  return (
    <SectionCard title={t('settings.about.title')}>
      <DetailList
        items={[
          { id: 'app', label: t('settings.about.appName'), value: info.appName },
          {
            id: 'version',
            label: t('settings.about.version'),
            value: info.version ? (
              <span dir="ltr">{info.version}</span>
            ) : (
              t('settings.about.version.unstamped')
            ),
          },
          {
            id: 'mode',
            label: t('settings.about.mode'),
            value:
              info.mode === 'preview'
                ? t('settings.general.mode.preview')
                : t('settings.general.mode.live'),
          },
          {
            id: 'environment',
            label: t('settings.about.environment'),
            value: info.environment ?? t('settings.about.environment.unstamped'),
          },
          { id: 'api', label: t('settings.about.api'), value: configured(info.apiConfigured) },
          { id: 'auth', label: t('settings.about.auth'), value: configured(info.authConfigured) },
        ]}
      />
      <p className="mt-5 max-w-3xl text-caption text-gray-600">{t('settings.about.claims')}</p>
    </SectionCard>
  );
}
