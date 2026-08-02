/**
 * Framework-agnostic signal from the API client to the auth layer: "a
 * request that should have been authenticated came back 401 while we
 * believed a live session was active." Kept as a plain event emitter
 * (not a React import) so `client.ts` never depends on React/AuthContext —
 * `AuthContext` is the only subscriber, and reacts by clearing state and
 * routing through the existing session-expired page.
 */
type Listener = () => void;

const listeners = new Set<Listener>();

export function onUnauthorizedResponse(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function emitUnauthorizedResponse(): void {
  for (const listener of listeners) listener();
}
