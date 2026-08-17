/**
 * Path constants for every route in the IA (§7 Screen Hierarchy). The
 * single source of truth for path strings — routes.tsx, navConfig.ts, and
 * every `navigate()`/`<Link>` call reference these instead of repeating
 * literal strings.
 */
export const ROUTES = {
  login: '/login',
  forgotPassword: '/forgot-password',
  resetPassword: '/reset-password',
  inviteAccept: '/invite/:token',
  sessionExpired: '/session-expired',
  accessDenied: '/access-denied',

  dashboard: '/dashboard',

  reports: '/reports',
  reportDetail: '/reports/:id',

  documents: '/documents',
  documentDetail: '/documents/:id',
  documentUpload: '/documents/upload',

  engagements: '/engagements',
  engagementDetail: '/engagements/:id',

  analysis: '/analysis',
  analysisRun: '/analysis/:runId',

  hubZero: '/hub-zero',
  carbon: '/carbon',
  telemetry: '/telemetry',

  organizations: '/organizations',
  organizationDetail: '/organizations/:id',

  users: '/users',
  frameworks: '/frameworks',
  audit: '/audit',
  settings: '/settings',

  notifications: '/notifications',
  profile: '/profile',
} as const;

export type RouteKey = keyof typeof ROUTES;
