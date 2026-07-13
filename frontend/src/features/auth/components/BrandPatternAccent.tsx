/** Static CSS-only environmental data network used behind the auth brand
 * panel. It has no semantic content and mirrors through logical positioning. */
export function BrandPatternAccent() {
  return (
    <div className="auth-brand-network" aria-hidden>
      <span className="auth-network-node auth-network-node-one" />
      <span className="auth-network-node auth-network-node-two" />
      <span className="auth-network-node auth-network-node-three" />
    </div>
  );
}
