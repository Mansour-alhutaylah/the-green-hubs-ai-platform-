import type { Session } from '../types';
import { Role } from '@/features/rbac/roles';
import { DEMO_WORKSPACE_ORG_ID } from '@/features/organizations/mockOrgs';
import { isDevAuthBypassEnabled } from '../devAuthBypass';
import {
  ChallengeExpiredError,
  InvalidCredentialsError,
  InvalidOtpError,
  RateLimitedError,
  type AuthService,
  type LoginResult,
} from './AuthService';
import { DEMO_PASSWORD, DEMO_USERS, findDemoUserByEmail } from './demoUsers';
import {
  clearPersistedSession,
  readPersistedSession,
  writePersistedSession,
} from './sessionStorage';

/** Fixed dev-mode OTP — shown as a hint on the OTP screen (§0.5: no real
 * SMS delivery exists yet, and the spec itself only assumes "OTP second
 * factor", not a specific provider). */
export const DEV_OTP_CODE = '123456';

/** The one place a submitted code is checked against the dev-mode OTP —
 * both `verifyOtp` below and InviteAcceptPage (which has no seeded invite
 * token to run a full `verifyOtp` challenge against) call this instead of
 * each re-implementing the comparison. */
export function isValidDevOtp(code: string): boolean {
  return code === DEV_OTP_CODE;
}

const MAX_ATTEMPTS = 3;
const LOCKOUT_MS = 5 * 60 * 1000; // §9.1: "fail x3 -> lock 5 min"
const CHALLENGE_TTL_MS = 10 * 60 * 1000;
const SESSION_TTL_MS = 12 * 60 * 60 * 1000;
const LOCAL_DEMO_TOKEN = 'local-development-demo-session';

interface PendingChallenge {
  email: string;
  createdAt: number;
}

const failedAttempts = new Map<string, { count: number; lockedUntil: number | null }>();
const pendingChallenges = new Map<string, PendingChallenge>();

function maskEmail(email: string): string {
  const [local, domain] = email.split('@');
  if (!local || !domain) return email;
  return `${local[0]}•••@${domain}`;
}

function randomId(): string {
  return crypto.randomUUID();
}

class MockAuthService implements AuthService {
  async requestLogin(email: string, password: string): Promise<LoginResult> {
    await delay();
    const normalizedEmail = email.trim().toLowerCase();
    const attempt = failedAttempts.get(normalizedEmail);

    if (attempt?.lockedUntil && attempt.lockedUntil > Date.now()) {
      throw new RateLimitedError(Math.ceil((attempt.lockedUntil - Date.now()) / 1000));
    }

    const user = findDemoUserByEmail(normalizedEmail);
    const isValid = user != null && password === DEMO_PASSWORD;

    if (!isValid) {
      const nextCount = (attempt?.count ?? 0) + 1;
      const lockedUntil = nextCount >= MAX_ATTEMPTS ? Date.now() + LOCKOUT_MS : null;
      failedAttempts.set(normalizedEmail, { count: nextCount, lockedUntil });
      if (lockedUntil) {
        throw new RateLimitedError(Math.ceil(LOCKOUT_MS / 1000));
      }
      throw new InvalidCredentialsError();
    }

    failedAttempts.delete(normalizedEmail);
    const challengeId = randomId();
    pendingChallenges.set(challengeId, { email: normalizedEmail, createdAt: Date.now() });

    return { kind: 'otpRequired', challengeId, maskedContact: maskEmail(normalizedEmail) };
  }

  async verifyOtp(challengeId: string, code: string): Promise<Session> {
    await delay();
    const challenge = pendingChallenges.get(challengeId);
    if (!challenge) throw new ChallengeExpiredError();
    if (Date.now() - challenge.createdAt > CHALLENGE_TTL_MS) {
      pendingChallenges.delete(challengeId);
      throw new ChallengeExpiredError();
    }
    if (!isValidDevOtp(code)) {
      throw new InvalidOtpError();
    }

    const user = findDemoUserByEmail(challenge.email);
    if (!user) throw new ChallengeExpiredError();

    pendingChallenges.delete(challengeId);

    const session: Session = {
      kind: 'demo',
      user,
      token: randomId(),
      expiresAt: Date.now() + SESSION_TTL_MS,
      activeOrgId: user.orgIds[0] ?? '',
    };
    writePersistedSession(session);
    return session;
  }

  async resendOtp(challengeId: string): Promise<void> {
    await delay();
    const challenge = pendingChallenges.get(challengeId);
    if (!challenge) throw new ChallengeExpiredError();
    challenge.createdAt = Date.now();
  }

  async enterDemoWorkspace(): Promise<Session> {
    if (!isDevAuthBypassEnabled()) {
      throw new Error('Development authentication bypass is disabled.');
    }

    const user = DEMO_USERS.find((candidate) => candidate.role === Role.Admin);
    if (!user) {
      throw new Error('No Admin demo user is configured.');
    }

    const session: Session = {
      kind: 'demo',
      user,
      token: LOCAL_DEMO_TOKEN,
      expiresAt: Date.now() + SESSION_TTL_MS,
      activeOrgId: DEMO_WORKSPACE_ORG_ID,
    };
    writePersistedSession(session);
    return session;
  }

  async logout(): Promise<void> {
    await delay(100);
    clearPersistedSession();
  }

  getSession(): Session | null {
    return readPersistedSession();
  }

  setActiveOrg(orgId: string): Session | null {
    const session = readPersistedSession();
    if (!session) return null;
    const updated: Session = { ...session, activeOrgId: orgId };
    writePersistedSession(updated);
    return updated;
  }

  getDevOtpHint(): string | null {
    return DEV_OTP_CODE;
  }

  checkDevOtpCode(code: string): boolean {
    return isValidDevOtp(code);
  }
}

function delay(ms = 350): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export const mockAuthService: AuthService = new MockAuthService();
