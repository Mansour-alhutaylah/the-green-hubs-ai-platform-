import { Badge, Button, Icon, SectionCard, Select } from '@/design-system';
import { useAuth } from '@/features/auth/useAuth';
import { useWorkspace } from '@/features/organizations/workspace/WorkspaceContext';
import { ROLE_LABELS } from '@/features/rbac/roles';
import { DetailList } from '@/features/workspace/components/DetailList';
import { useApplicationInfo, useIntegrationCapabilities } from '@/lib/data/hooks/useApplicationInfo';
import type { IntegrationCapability } from '@/lib/data/contracts';
import { AVAILABLE_LOCALES, hasSelectableLocales } from '@/lib/i18n/availability';
import type { Locale } from '@/lib/i18n/context';
import type { StringKey } from '@/lib/i18n/strings/en';
import { useLocale } from '@/lib/i18n/useLocale';
import { PageHeader } from '@/shell/PageHeader';

const ANCHORS = ['general', 'language', 'residency', 'security', 'integrations', 'about'] as const;
type Anchor = (typeof ANCHORS)[number];

const ANCHOR_LABEL_KEY: Record<Anchor, StringKey> = {
  general: 'settings.section.general',
  language: 'settings.section.language',
  residency: 'settings.section.residency',
  security: 'settings.section.security',
  integrations: 'settings.section.integrations',
  about: 'settings.section.about',
};

/**
 * Settings. Admin+ route (the router's `RoleGuard` covers it).
 *
 * Every section answers its question with a fact, or says plainly that the
 * product cannot answer it. The rule the page is built around:
 *
 * > A Settings screen is visible to any signed-in user who can reach the
 * > route. Nothing on it may be an infrastructure identifier.
 *
 * So no section renders a database host, a Supabase project URL or
 * reference, a DSN, a bucket, an API origin, a region, an account or
 * service identifier, a key name, or any credential. Configuration presence
 * is reported as a boolean and never as a value — see `useApplicationInfo`,
 * whose contract has no field for any of them, which is what makes the
 * absence structural rather than a matter of care here.
 *
 * Data residency has no product API at all, so it renders a precise
 * unavailable state rather than naming a region it cannot verify.
 * Multi-factor authentication is stated as not implemented, and the mock
 * verification-code flow a previous audit removed is not restored. n8n is
 * neither contacted nor listed.
 */
export function SettingsPage() {
  const { t } = useLocale();

  return (
    <div>
      <PageHeader
        eyebrow={t('settings.eyebrow')}
        title={t('nav.settings')}
        subtitle={t('settings.subtitle')}
      />

      <div className="flex flex-col gap-8 lg:flex-row lg:gap-10">
        {/* A scrollable horizontal strip on a phone, a rail from `lg` up —
            neither shape pushes the page sideways at 360px. */}
        <nav aria-label={t('settings.nav.label')} className="lg:w-52 lg:shrink-0">
          <ul className="flex gap-1 overflow-x-auto pb-1 text-body text-gray-600 lg:flex-col lg:overflow-visible lg:pb-0">
            {ANCHORS.map((anchor) => (
              <li key={anchor} className="shrink-0">
                <a
                  href={`#${anchor}`}
                  className="block whitespace-nowrap rounded-s px-3 py-2 hover:bg-tint-100 hover:text-forest-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-forest-700"
                >
                  {t(ANCHOR_LABEL_KEY[anchor])}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="flex min-w-0 flex-1 flex-col gap-6">
          <GeneralSection />
          <LanguageSection />
          <ResidencySection />
          <SecuritySection />
          <IntegrationsSection />
          <AboutSection />
        </div>
      </div>
    </div>
  );
}

/** Real identity and real workspace context, both server-resolved. */
function GeneralSection() {
  const { t } = useLocale();
  const { user, sessionKind } = useAuth();
  const workspace = useWorkspace();
  const info = useApplicationInfo(t('brand.name'));

  const modeLabel =
    info.mode === 'preview' ? t('settings.general.mode.preview') : t('settings.general.mode.live');
  const modeDescription =
    info.mode === 'preview'
      ? t('settings.general.mode.preview.description')
      : t('settings.general.mode.live.description');

  return (
    <section id="general">
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
              id: 'organization',
              label: t('settings.general.field.organization'),
              value: (
                <span data-user-content>
                  {workspace.organization?.name ?? t('settings.general.organization.missing')}
                </span>
              ),
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
                    {modeLabel}
                  </Badge>
                  <span className="mt-1 block text-caption text-gray-600">{modeDescription}</span>
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
    </section>
  );
}

/**
 * Language.
 *
 * The MVP ships English only, so this section is a statement rather than a
 * control. There is no selector, because a selector implies a choice, and
 * the only other dictionary in the tree is incomplete — offering it would
 * hand a reviewer a half-translated interface and call it a feature.
 *
 * What *is* offered is the truth: English is the current product language,
 * and Arabic with right-to-left layout is deferred to a dedicated later
 * phase. When `AVAILABLE_LOCALES` gains a second entry, the control below
 * returns and `LocaleProvider` — which already sets
 * `document.documentElement.lang` and `dir` in one effect — flips the whole
 * interface without a reload. None of that machinery was removed to get
 * here.
 */
function LanguageSection() {
  const { t, locale, setLocale } = useLocale();
  const selectable = hasSelectableLocales();

  return (
    <section id="language">
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
                  available === 'ar'
                    ? t('settings.language.arabic')
                    : t('settings.language.english'),
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
    </section>
  );
}

/**
 * Data residency.
 *
 * No product API exposes residency metadata. The honest rendering of a fact
 * nobody publishes is a precise unavailable state — not a region name, not
 * a provider, and not a reassurance this application has no way to verify.
 */
function ResidencySection() {
  const { t } = useLocale();
  return (
    <section id="residency">
      <SectionCard className="border-dashed" title={t('settings.residency.title')}>
        <p className="text-body font-bold text-ink-900">
          {t('settings.residency.unavailable.title')}
        </p>
        <p className="mt-2 max-w-3xl text-body text-gray-600">
          {t('settings.residency.unavailable.description')}
        </p>
      </SectionCard>
    </section>
  );
}

/**
 * Session summary, the existing sign-out action, and a truthful statement
 * about multi-factor authentication.
 *
 * MFA administration is not implemented anywhere in this product: nothing
 * enrols a factor, nothing verifies one, and no endpoint exists to turn one
 * on. A toggle here would be inert, so there is none — the sentence is the
 * whole subsection.
 */
function SecuritySection() {
  const { t } = useLocale();
  const { user, sessionKind, logout } = useAuth();

  return (
    <section id="security">
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
    </section>
  );
}

const INTEGRATION_LABEL_KEY: Record<IntegrationCapability['id'], StringKey> = {
  documentStorage: 'settings.integrations.documentStorage',
  documentAnalysis: 'settings.integrations.documentAnalysis',
  authentication: 'settings.integrations.authentication',
};

/**
 * Capabilities, not connections.
 *
 * Each row names something the product does. None names a provider, an
 * address, an account, a key, or a connection string — none of that belongs
 * on a screen, and none of it is exposed by any product API. Every row is
 * "not configurable here", which is the literal truth: no endpoint exists
 * to configure any of it, so a control would do nothing.
 *
 * Workflow automation (n8n) is absent from this list on purpose. This
 * application never contacts it and the product API says nothing about it,
 * so listing it would imply a connection the Frontend cannot verify.
 */
function IntegrationsSection() {
  const { t } = useLocale();
  const capabilities = useIntegrationCapabilities();

  return (
    <section id="integrations">
      <SectionCard
        title={t('settings.integrations.title')}
        description={t('settings.integrations.description')}
      >
        <ul className="flex flex-col gap-3">
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
    </section>
  );
}

/**
 * About.
 *
 * The application name, the version this build was stamped with (or a
 * statement that it carries none), the mode, and the build classification.
 * The two configuration rows are booleans — "Configured" / "Not
 * configured" — never the URL or key behind them.
 *
 * No certification, uptime, availability, or compliance claim appears, and
 * the closing line says so: an unbacked assurance on an About screen is the
 * kind of claim that ends up quoted in a procurement document.
 */
function AboutSection() {
  const { t } = useLocale();
  const info = useApplicationInfo(t('brand.name'));

  const configured = (value: boolean) =>
    value ? t('settings.about.configured') : t('settings.about.notConfigured');

  return (
    <section id="about">
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
    </section>
  );
}
