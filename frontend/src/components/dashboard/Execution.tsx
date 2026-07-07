import type { VHEState } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function Execution({ state, postControl }: { state: VHEState; postControl: (e: string) => Promise<void> }) {
  const fills = [...(state.fills ?? [])].reverse().slice(0, 25);
  return (
    <div className="p-3 sm:p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold font-sans text-text-primary">Paper Fill Tape</h2>
        <button onClick={() => postControl("/api/control/demo-fill").catch(console.error)}
          className="px-3 py-1.5 rounded-lg border border-white/15 text-text-muted text-xs font-sans font-semibold hover:bg-white/5 transition-colors">
          Demo Fill
        </button>
      </div>
      {fills.length === 0 ? (
        <p className="text-text-muted font-mono text-sm">No fills yet.</p>
      ) : (
        <div className="bg-bg-card rounded-xl border border-white/[0.08] overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono font-bold text-text-faint uppercase border-b border-white/[0.06]">
                  <th className="text-left px-4 py-2">Time</th>
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-right px-4 py-2">Side</th>
                  <th className="text-right px-4 py-2">Price</th>
                  <th className="text-right px-4 py-2">Qty</th>
                  <th className="text-right px-4 py-2">Reason</th>
                </tr>
              </thead>
              <tbody>
                {fills.map((f) => (
                  <tr key={f.fill_id} className="border-t border-white/[0.04]">
                    <td className="px-4 py-2 font-mono text-text-faint text-xs">
                      {new Date(f.filled_at).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })}
                    </td>
                    <td className="px-4 py-2 font-mono font-semibold text-text-primary">{f.symbol}</td>
                    <td className={`px-4 py-2 font-mono font-bold text-right ${f.side === "BUY" ? "text-vhe-green" : "text-vhe-red"}`}>{f.side}</td>
                    <td className="px-4 py-2 font-mono text-right">{INR.format(f.price)}</td>
                    <td className="px-4 py-2 font-mono text-right text-text-muted">{f.quantity}</td>
                    <td className="px-4 py-2 font-mono text-right text-text-faint text-xs">{f.reason}</td>
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
