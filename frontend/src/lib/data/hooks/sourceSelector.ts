/**
 * The shape every F2A source selector returns, and the reasoning shared by
 * all of them.
 *
 * Each selector looks like this:
 *
 * ```ts
 * const live = useLiveX(!preview);   // hook always called, gated by `enabled`
 * return preview ? readPreviewX() : live;
 * ```
 *
 * The gating rather than branching is deliberate. `isPreviewMode()` reads
 * only build-time environment values, so it is constant for the life of a
 * build and the hook order never varies — but calling the Live hook
 * unconditionally keeps that true *structurally*, not just in practice.
 * With `enabled: false` the Live hook creates no `AbortController` and
 * issues no request, so a Preview render costs one `useState` pair and
 * touches nothing.
 *
 * The reverse direction is enforced twice over: every `readPreview*`
 * asserts the build mode and throws in Live, and the `live/` sources import
 * no fixture module at all, so there is no Preview value in scope for a
 * Live failure to fall back to.
 *
 * Selectors are split one file per domain rather than gathered into a
 * single workspace module. A page that needs engagements should not pull
 * the organization, team, and dashboard sources — and their endpoint
 * clients, adapters, and fixtures — into its bundle on the way.
 */
export interface WorkspaceResource<T> {
  readonly state: T;
  readonly retry: () => void;
}

/** Preview resolves synchronously, so its retry is a no-op — there is
 * nothing that could have failed transiently. */
export const NO_RETRY = () => {};
