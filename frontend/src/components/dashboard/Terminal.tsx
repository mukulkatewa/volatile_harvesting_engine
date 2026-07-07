import { Activity, PauseCircle, PlayCircle, RotateCcw, Skull, Zap } from "lucide-react";
import type { VHEState } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const PCT = (v: number) => `${(v * 100).toFixed(2)}%`;

interface Props { state: VHEState; postControl: (endpoint: string) => Promise<void> }

const CONTROLS = [
  { label: "Pause",     endpoint: "/api/control/pause",       icon: PauseCircle, cls: "border-vhe-amber/30 text-vhe-amber hover:bg-vhe-amber/10" },
  { label: "Resume",    endpoint: "/api/control/resume",      icon: PlayCircle,  cls: "border-vhe-green/30 text-vhe-green hover:bg-vhe-green/10" },
  { label: "Kill",      endpoint: "/api/control/kill",        icon: Skull,       cls: "border-vhe-red/30 text-vhe-red hover:bg-vhe-red/10" },
  { label: "Demo Fill", endpoint: "/api/control/demo-fill",   icon: Zap,         cls: "border-white/15 text-text-muted hover:bg-white/5" },
  { label: "Reset",     endpoint: "/api/control/reset-paper", icon: RotateCcw,   cls: "border-white/15 text-text-muted hover:bg-white/5" },
];

export function Terminal({ state, postControl }: Props) {
  const p = state.portfolio;
  const ctrl = state.controls;
  const equity = p.equity ?? p.cash ?? 0;
  const pnl = equity - 75000;
  const pnlPos = pnl >= 0;

  const statCards = [
    { label: "Equity",        value: INR.format(equity),              cls: "text-text-primary" },
    { label: "Session P&L",   value: INR.format(pnl),                 cls: pnlPos ? "text-vhe-green" : "text-vhe-red", glow: pnlPos },
    { label: "Gross Exposure",value: INR.format(p.gross_exposure ?? 0), cls: "text-text-primary" },
    { label: "Exposure %",    value: PCT(p.gross_exposure_pct ?? 0),  cls: "text-text-primary" },
  ];

  return (
    <div className="p-6 space-y-5">
      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {statCards.map(({ label, value, cls, glow }) => (
          <div
            key={label}
            className="relative overflow-hidden bg-gradient-to-br from-bg-card to-bg-panel rounded-xl border border-white/[0.08] p-4"
          >
            {glow && (
              <div className="absolute inset-0 bg-vhe-green/[0.04] pointer-events-none" />
            )}
            <div className="text-[10px] font-mono font-bold text-text-faint uppercase tracking-wider">{label}</div>
            <div className={`text-xl font-mono font-semibold mt-1.5 ${cls}`}>{value}</div>
          </div>
        ))}
      </div>

      {/* Risk alert badges */}
      {(ctrl.kill_switch || ctrl.automation_paused || ctrl.last_risk_reject) && (
        <div className="flex gap-2 flex-wrap">
          {ctrl.kill_switch && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-xs font-mono font-bold">
              <Skull className="w-3 h-3" /> KILL SWITCH
            </span>
          )}
          {ctrl.automation_paused && (
            <span className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-vhe-amber/10 border border-vhe-amber/30 text-vhe-amber text-xs font-mono font-bold">
              <PauseCircle className="w-3 h-3" /> PAUSED
            </span>
          )}
          {ctrl.last_risk_reject && (
            <span className="px-3 py-1 rounded-full bg-bg-card border border-white/10 text-text-muted text-xs font-mono">
              Last reject: {ctrl.last_risk_reject}
            </span>
          )}
        </div>
      )}

      {/* Control buttons */}
      <div className="flex gap-2 flex-wrap">
        {CONTROLS.map(({ label, endpoint, icon: Icon, cls }) => (
          <button
            key={label}
            onClick={() => postControl(endpoint)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-sans font-semibold transition-colors ${cls}`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Live quotes */}
      {Object.keys(state.quotes).length > 0 && (
        <div className="bg-gradient-to-br from-bg-card to-bg-panel rounded-xl border border-white/[0.08] overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06]">
            <Activity className="w-3.5 h-3.5 text-vhe-green" />
            <span className="text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider">Live Quotes</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono font-bold text-text-faint uppercase border-b border-white/[0.04]">
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-right px-4 py-2">LTP</th>
                  <th className="text-right px-4 py-2">Regime</th>
                </tr>
              </thead>
              <tbody>
                {Object.values(state.quotes).map((q) => (
                  <tr key={q.symbol} className="border-t border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                    <td className="px-4 py-2.5 font-mono font-semibold text-text-primary">{q.symbol}</td>
                    <td className="px-4 py-2.5 font-mono text-right text-vhe-green">{INR.format(q.ltp)}</td>
                    <td className="px-4 py-2.5 font-mono text-right text-text-muted text-xs capitalize">
                      {state.plans?.[q.symbol]?.regime ?? "—"}
                    </td>
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
