import type { AppMode } from '../source';

/**
 * The application facts Settings is allowed to state.
 *
 * This contract exists to make the *absence* of infrastructure identifiers
 * structural rather than a matter of reviewer vigilance. There is no field
 * here for a database host, a Supabase project reference, a DSN, a bucket
 * name, an API origin, a service identifier, a key name, or a region — so
 * no Settings component can render one, however carelessly it is written.
 *
 * Configuration presence is reported as a **boolean**, never as a value.
 * "An API base URL is configured" is a useful, safe operational fact;
 * printing the URL itself would disclose the deployment's topology to
 * every signed-in viewer, including a Viewer-tier one.
 *
 * `residencyStatement` is intentionally absent for the same reason: no
 * product API exposes data-residency metadata, and the honest rendering of
 * a fact nobody publishes is an unavailable state, not a guess.
 */
export interface ApplicationInfo {
  /** The product name, from the translated brand dictionary. */
  readonly appName: string;
  /** Live or Preview, resolved from the build-time mode. */
  readonly mode: AppMode;
  /**
   * The build classification (`production` | `preview` | `development`) as
   * declared at build time, or `null` when the build declared none. This
   * is a category, not an environment identifier — it names no host,
   * project, or account.
   */
  readonly environment: string | null;
  /** Semantic version this build was stamped with, or `null` when the
   * build stamped none. Never invented. */
  readonly version: string | null;
  /** Whether an API base URL is configured — the boolean only. */
  readonly apiConfigured: boolean;
  /** Whether browser-side authentication is configured — the boolean
   * only. Never the project URL and never any key. */
  readonly authConfigured: boolean;
}

/**
 * The integration capabilities the product can truthfully describe.
 *
 * Each entry is a *capability*, not a connection: no endpoint, credential,
 * key name, private URL, or connection string is modelled, and
 * `state: 'not-configurable'` is the honest answer for every capability
 * whose administration has no product API today.
 */
export type IntegrationState = 'available' | 'not-configurable';

export interface IntegrationCapability {
  readonly id: 'documentStorage' | 'documentAnalysis' | 'authentication';
  readonly state: IntegrationState;
}
