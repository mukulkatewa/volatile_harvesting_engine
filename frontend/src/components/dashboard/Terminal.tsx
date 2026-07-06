import type { VHEState } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const PCT = (v: number) => `${(v * 100).toFixed(2)}%`;

interface Props { state: VHEState; postControl: (endpoint: string) => Promise<void> }

export function Terminal({ state, postControl }: Props) {
  const p = state.portfolio;
  const ctrl = state.controls;
  const equity = p.equity ?? p.cash ?? 0;
  const pnl = equity - 75000;
  const pnlCls = pnl >= 0 ? "text-vhe-green" : "text-vhe-red";

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Equity", value: INR.format(equity), cls: "" },
          { label: "Session P&L", value: INR.format(pnl), cls: pnlCls },
          { label: "Gross Exposure", value: INR.format(p.gross_exposure ?? 0), cls: "" },
          { label: "Exposure %", value: PCT(p.gross_exposure_pct ?? 0), cls: "" },
        ].map(({ label, value, cls }) => (
          <div key={label} className="bg-bg-card rounded-xl border border-white/[0.08] p-4">
            <div className="text-[10px] font-mono font-bold text-text-muted uppercase tracking-wider">{label}</div>
            <div className={`text-xl font-mono font-semibold mt-1 ${cls || "text-text-primary"}`}>{value}</div>
          </div>
        ))}
      </div>

      {(ctrl.kill_switch || ctrl.automation_paused || ctrl.last_risk_reject) && (
        <div className="flex gap-3 flex-wrap">
          {ctrl.kill_switch && (
            <span className="px-3 py-1 rounded-full bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-xs font-mono font-bold">KILL SWITCH</span>
          )}
          {ctrl.automation_paused && (
            <span className="px-3 py-1 rounded-full bg-vhe-amber/10 border border-vhe-amber/30 text-vhe-amber text-xs font-mono font-bold">PAUSED</span>
          )}
          {ctrl.last_risk_reject && (
            <span className="px-3 py-1 rounded-full bg-bg-card border border-white/10 text-text-muted text-xs font-mono">Last reject: {ctrl.last_risk_reject}</span>
          )}
        </div>
      )}

      <div className="flex gap-2 flex-wrap">
        {[
          { label: "Pause",     endpoint: "/api/control/pause",       cls: "border-vhe-amber/30 text-vhe-amber hover:bg-vhe-amber/10" },
          { label: "Resume",    endpoint: "/api/control/resume",      cls: "border-vhe-green/30 text-vhe-green hover:bg-vhe-green/10" },
          { label: "Kill",      endpoint: "/api/control/kill",        cls: "border-vhe-red/30 text-vhe-red hover:bg-vhe-red/10" },
          { label: "Demo Fill", endpoint: "/api/control/demo-fill",   cls: "border-white/15 text-text-muted hover:bg-white/5" },
          { label: "Reset",     endpoint: "/api/control/reset-paper", cls: "border-white/15 text-text-muted hover:bg-white/5" },
        ].map(({ label, endpoint, cls }) => (
          <button key={label} onClick={() => postControl(endpoint)}
            className={`px-3 py-1.5 rounded-lg border text-xs font-sans font-semibold transition-colors ${cls}`}>
            {label}
          </button>
        ))}
      </div>

      {Object.keys(state.quotes).length > 0 && (
        <div className="bg-bg-card rounded-xl border border-white/[0.08] overflow-hidden">
          <div className="px-4 py-3 border-b border-white/[0.06] text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider">Live Quotes</div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono font-bold text-text-faint uppercase">
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-right px-4 py-2">LTP</th>
                  <th className="text-right px-4 py-2">Regime</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(state.quotes).map((q) => (
                  <tr key={q.symbol} className="border-t border-white/[0.04] hover:bg-white/[0.02]">
                    <td className="px-4 py-2 font-mono font-semibold text-text-primary">{q.symbol}</td>
                    <td className="px-4 py-2 font-mono text-right text-vhe-green">{INR.format(q.ltp)}</td>
                    <td className="px-4 py-2 font-mono text-right text-text-muted text-xs">{state.plans?.[q.symbol]?.regime ?? "—"}</td>
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
