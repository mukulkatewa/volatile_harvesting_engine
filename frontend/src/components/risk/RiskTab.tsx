import { MonteCarloPanel } from "./MonteCarloPanel";
import { WalkForwardPanel } from "./WalkForwardPanel";

export function RiskTab() {
  return (
    <div className="p-6 space-y-12">
      <MonteCarloPanel />
      <div className="border-t border-white/[0.08]" />
      <WalkForwardPanel />
    </div>
  );
}
