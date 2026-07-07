import type { VHEState } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function Strategies({ state }: { state: VHEState }) {
  const plans = Object.values(state.plans ?? {});
  return (
    <div className="p-3 sm:p-6 space-y-6">
      <h2 className="text-lg font-bold font-sans text-text-primary">Grid Plans</h2>
      {plans.length === 0 ? (
        <p className="text-text-muted font-mono text-sm">No active grid plans.</p>
      ) : (
        <div className="bg-bg-card rounded-xl border border-white/[0.08] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono font-bold text-text-faint uppercase border-b border-white/[0.06]">
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-right px-4 py-2">Regime</th>
                  <th className="text-right px-4 py-2">Fair Value</th>
                  <th className="text-right px-4 py-2">LTP</th>
                  <th className="text-right px-4 py-2">Levels</th>
                </tr>
              </thead>
              <tbody>
                {plans.map((p) => (
                  <tr key={p.symbol} className="border-t border-white/[0.04]">
                    <td className="px-4 py-2 font-mono font-semibold text-text-primary">{p.symbol}</td>
                    <td className="px-4 py-2 font-mono text-right text-xs text-text-muted">{p.regime}</td>
                    <td className="px-4 py-2 font-mono text-right">{INR.format(p.fair_value)}</td>
                    <td className="px-4 py-2 font-mono text-right text-vhe-green">{INR.format(p.current_price)}</td>
                    <td className="px-4 py-2 font-mono text-right text-text-muted">{p.levels_filled}/{p.total_levels}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
