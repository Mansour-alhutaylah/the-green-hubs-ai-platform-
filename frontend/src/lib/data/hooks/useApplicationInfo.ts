import type {
  ApplicationInfo,
  IntegrationCapability,
} from '../contracts/application';
import { getAppMode } from '../source';

/**
 * The settings-safe application facts.
 *
 * Everything here is read from build-time configuration and reported as a
 * *category* or a *boolean*. Deliberately absent, and absent by
 * construction rather than by omission (the `ApplicationInfo` contract has
 * no field for any of them): database hosts, the Supabase project URL or
 * reference, DSNs, bucket names, API origins, regions, account or service
 * identifiers, key names, and every credential.
 *
 * "Is an API base URL configured?" is a useful operational fact a Settings
 * screen may state. The URL itself is deployment topology, and a Settings
 * page is visible to any signed-in user with the tier to reach it, so the
 * value never leaves this module — only `Boolean(...)` of it does.
 */

const KNOWN_ENVIRONMENTS: readonly string[] = ['production', 'preview', 'development'];

/** A declared build classification, or `null`. An unrecognized value is
 * reported as `null` rather than echoed: a free-form environment string
 * could carry a deployment or account name. */
function readEnvironment(): string | null {
  const raw = import.meta.env.VITE_APP_ENVIRONMENT;
  if (typeof raw !== 'string') return null;
  return KNOWN_ENVIRONMENTS.includes(raw) ? raw : null;
}

/** The version this build was stamped with, or `null`. Never derived,
 * never defaulted to a plausible-looking number — an unstamped build says
 * so, and the About section renders that as a stated absence. */
function readVersion(): string | null {
  const raw = import.meta.env.VITE_APP_VERSION;
  return typeof raw === 'string' && raw.trim().length > 0 ? raw.trim() : null;
}

export function useApplicationInfo(appName: string): ApplicationInfo {
  return {
    appName,
    mode: getAppMode(),
    environment: readEnvironment(),
    version: readVersion(),
    // `Boolean(...)`, never the value.
    apiConfigured: Boolean(import.meta.env.VITE_API_BASE_URL),
    authConfigured: Boolean(
      import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY,
    ),
  };
}

/**
 * The integration capabilities the product can describe truthfully.
 *
 * These are *capabilities*, not connections. Document storage, document
 * analysis, and authentication are real, shipped parts of the product, so
 * a Settings reader may be told they exist. Nothing states which provider
 * backs them, at which address, under which account, or with which
 * credential — none of which any product API exposes, and none of which
 * belongs on a screen.
 *
 * Everything administrative is `not-configurable`, which is the literal
 * truth: no endpoint exists to configure any of it, so there is no control
 * to render and no toggle that would do anything.
 *
 * Workflow automation (n8n) is absent from this list entirely. The product
 * API exposes nothing about it, this application never contacts it, and
 * listing it would imply a connection the Frontend neither has nor can
 * verify.
 */
export function useIntegrationCapabilities(): readonly IntegrationCapability[] {
  return [
    { id: 'documentStorage', state: 'not-configurable' },
    { id: 'documentAnalysis', state: 'not-configurable' },
    { id: 'authentication', state: 'not-configurable' },
  ];
}
