import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../../api/client";
import type { MonteCarloResult } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function MonteCarloPanel() {
  const [symbol, setSymbol] = useState("");
  const [barsFile, setBarsFile] = useState("");
  const [nSims, setNSims] = useState(5000);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MonteCarloResult | null>(null);

  const run = async () => {
    if (!symbol.trim() || !barsFile.trim()) { setError("Symbol and bars_file required"); return; }
    setError(null); setLoading(true);
    try {
      const r = await api.runMonteCarlo({ symbol: symbol.trim().toUpperCase(), bars_file: barsFile.trim(), n_sims: nSims, initial_capital: 75000 });
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally { setLoading(false); }
  };

  const pctData = result
    ? Object.entries(result.pnl_percentiles).map(([k, v]) => ({ label: k.toUpperCase(), value: v }))
    : [];

  const curveData = result?.equity_curves?.[0]?.map((_, i) => ({
    trade: i,
    ...Object.fromEntries(result.equity_curves.slice(0, 20).map((c, j) => [`s${j}`, c[i]])),
    median: [...result.equity_curves.slice(0, 20).map((c) => c[i])].sort((a, b) => a - b)[10] ?? 0,
  })) ?? [];

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-bold font-sans text-text-primary">Monte Carlo Risk Analysis</h2>
      <div className="flex gap-2 flex-wrap">
        <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="Symbol e.g. RELIANCE"
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg placeholder:text-text-faint min-w-[180px]" />
        <input value={barsFile} onChange={(e) => setBarsFile(e.target.value)} placeholder="data/RELIANCE.csv"
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg placeholder:text-text-faint min-w-[200px]" />
        <input value={nSims} onChange={(e) => setNSims(Number(e.target.value))} type="number" min={100} max={100000}
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg w-28" />
        <button onClick={run} disabled={loading}
          className="px-4 py-2 rounded-lg bg-vhe-green/10 border border-vhe-green/30 text-vhe-green text-sm font-semibold font-sans hover:bg-vhe-green/20 disabled:opacity-50 transition-colors">
          {loading ? "Running…" : "Run MC"}
        </button>
      </div>
      {error && <div className="p-3 rounded-lg bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-sm font-mono">{error}</div>}
      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {[
              { label: "Median P&L",  value: INR.format(result.pnl_percentiles.p50), cls: result.pnl_percentiles.p50 >= 0 ? "text-vhe-green" : "text-vhe-red" },
              { label: "VaR 95%",     value: INR.format(result.var_95 - 75000),       cls: "text-vhe-red" },
              { label: "P(Ruin)",     value: `${(result.p_ruin * 100).toFixed(1)}%`,  cls: result.p_ruin < 0.05 ? "text-vhe-green" : result.p_ruin < 0.15 ? "text-vhe-amber" : "text-vhe-red" },
              { label: "Kelly f*",    value: `${(result.kelly_fraction * 100).toFixed(1)}%`, cls: "text-vhe-blue" },
              { label: "CVaR 95%",    value: INR.format(result.cvar_95 - 75000),      cls: "text-vhe-red" },
              { label: "Max DD P95",  value: `${(result.drawdown_p95 * 100).toFixed(1)}%`, cls: result.drawdown_p95 > 0.05 ? "text-vhe-amber" : "text-vhe-green" },
              { label: "Trade Count", value: String(result.trade_count),              cls: "text-text-primary" },
              { label: "Simulations", value: String(result.sim_count),               cls: "text-text-primary" },
            ].map(({ label, value, cls }) => (
              <div key={label} className="bg-bg-card rounded-xl border border-white/[0.08] p-4">
                <div className="text-[10px] font-mono font-bold text-text-muted uppercase tracking-wider">{label}</div>
                <div className={`text-xl font-mono font-semibold mt-1 ${cls}`}>{value}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-bg-card rounded-xl border border-white/[0.08] p-4">
              <div className="text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider mb-4">P&L Percentiles</div>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={pctData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis dataKey="label" tick={{ fill: "#8b97a8", fontSize: 11 }} />
                  <YAxis tick={{ fill: "#8b97a8", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#161d27", border: "1px solid rgba(148,163,184,0.15)", borderRadius: "8px" }} formatter={(v: number) => INR.format(v)} />
                  <Bar dataKey="value" fill="#387ed1" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="bg-bg-card rounded-xl border border-white/[0.08] p-4">
              <div className="text-[11px] font-mono font-bold text-text-muted uppercase tracking-wider mb-4">Equity Scenarios</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={curveData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" />
                  <XAxis dataKey="trade" tick={false} />
                  <YAxis tick={{ fill: "#8b97a8", fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: "#161d27", border: "1px solid rgba(148,163,184,0.15)", borderRadius: "8px" }} formatter={(v: number) => INR.format(v)} />
                  {Array.from({ length: Math.min(20, result.equity_curves.length) }, (_, j) => (
                    <Line key={j} type="monotone" dataKey={`s${j}`} stroke="rgba(56,126,209,0.2)" dot={false} strokeWidth={1} />
                  ))}
                  <Line type="monotone" dataKey="median" stroke="#00d09c" strokeWidth={2} dot={false} name="Median" />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
