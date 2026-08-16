import { isPreviewMode } from '@/lib/data/source';
import type { AuthService } from './AuthService';
import { liveAuthService } from './liveAuthService';
import { previewAuthService } from './previewAuthService';

/**
 * The app's real default `AuthService`, wired in by `AuthContext.tsx`
 * (every test injects its own service instead, so this module is not
 * exercised by the suite).
 *
 * The selection is a single build-time branch, not a per-call decision:
 * a Live build gets `liveAuthService` and nothing else, and a Preview build
 * gets `previewAuthService` and nothing else. The previous arrangement —
 * one composite service that delegated some methods to a mock and others to
 * the real Supabase client — is exactly what allowed a demo flow to sit
 * next to real authentication on the same screen. Preview and Live now
 * share no object, no storage, and no code path.
 */
export const resolvedAuthService: AuthService = isPreviewMode()
  ? previewAuthService
  : liveAuthService;
