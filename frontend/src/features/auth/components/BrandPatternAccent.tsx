/** Static CSS-only environmental data network used behind the auth brand
 * panel. It has no semantic content and mirrors through logical positioning. */
export function BrandPatternAccent() {
  return (
    <div className="auth-brand-network" aria-hidden>
      <span className="auth-network-node auth-network-node-one" />
      <span className="auth-network-node auth-network-node-two" />
      <span className="auth-network-node auth-network-node-three" />
      <span className="auth-sun" />
      <span className="auth-hill auth-hill-far" />
      <span className="auth-hill auth-hill-near" />
      <span className="auth-turbine auth-turbine-one">
        <i />
        <b />
        <em />
      </span>
      <span className="auth-turbine auth-turbine-two">
        <i />
        <b />
        <em />
      </span>
      <span className="auth-tree auth-tree-one">
        <i />
      </span>
      <span className="auth-tree auth-tree-two">
        <i />
      </span>
    </div>
  );
}
