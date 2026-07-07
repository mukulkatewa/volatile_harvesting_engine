import { useState } from "react";
import { api } from "../../api/client";
import type { WFResult } from "../../types/api";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function WalkForwardPanel() {
  const [symbol, setSymbol] = useState("");
  const [barsFile, setBarsFile] = useState("");
  const [trainDays, setTrainDays] = useState(60);
  const [testDays, setTestDays] = useState(15);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<WFResult | null>(null);

  const run = async () => {
    if (!symbol.trim() || !barsFile.trim()) { setError("Symbol and bars_file required"); return; }
    if (!trainDays || trainDays < 10) { setError("Train days must be at least 10"); return; }
    if (!testDays || testDays < 5) { setError("Test days must be at least 5"); return; }
    setError(null); setLoading(true);
    try {
      const r = await api.runWalkForward({ symbol: symbol.trim().toUpperCase(), bars_file: barsFile.trim(), train_days: trainDays, test_days: testDays });
      setResult(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally { setLoading(false); }
  };

  const verdictCls = result?.verdict === "Not overfit"
    ? "bg-vhe-green/10 border-vhe-green/30 text-vhe-green"
    : result?.verdict === "Marginal"
    ? "bg-vhe-amber/10 border-vhe-amber/30 text-vhe-amber"
    : "bg-vhe-red/10 border-vhe-red/30 text-vhe-red";

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-bold font-sans text-text-primary">Walk-Forward Validation</h2>
      <div className="flex flex-col sm:flex-row gap-2 flex-wrap">
        <input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="Symbol"
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg placeholder:text-text-faint w-full sm:w-auto sm:min-w-[160px]" />
        <input value={barsFile} onChange={(e) => setBarsFile(e.target.value)} placeholder="data/RELIANCE.csv"
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg placeholder:text-text-faint w-full sm:w-auto sm:min-w-[200px]" />
        <input value={trainDays} onChange={(e) => setTrainDays(Number(e.target.value))} type="number" min={10} max={250}
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg w-full sm:w-24" placeholder="Train days" />
        <input value={testDays} onChange={(e) => setTestDays(Number(e.target.value))} type="number" min={5} max={60}
          className="bg-bg-card border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg w-full sm:w-24" placeholder="Test days" />
        <button onClick={run} disabled={loading}
          className="px-4 py-2 rounded-lg bg-vhe-blue/10 border border-vhe-blue/30 text-vhe-blue text-sm font-semibold font-sans hover:bg-vhe-blue/20 disabled:opacity-50 transition-colors w-full sm:w-auto">
          {loading ? "Running…" : "Run WF"}
        </button>
      </div>
      {error && <div className="p-3 rounded-lg bg-vhe-red/10 border border-vhe-red/30 text-vhe-red text-sm font-mono">{error}</div>}
      {result && (
        <>
          <div className="flex gap-3 flex-wrap items-center">
            <span className={`px-4 py-1.5 rounded-full border text-xs font-mono font-bold ${verdictCls}`}>{result.verdict}</span>
            <span className="text-text-muted font-mono text-sm">WF Efficiency: <strong className="text-text-primary">{result.wf_efficiency.toFixed(3)}</strong></span>
            <span className="text-text-muted font-mono text-sm">Stable ATR Mult: <strong className="text-text-primary">{result.param_stability.atr_multiplier}</strong></span>
            <span className="text-text-muted font-mono text-sm">Stability: <strong className="text-text-primary">{(result.param_stability.stability_score * 100).toFixed(0)}%</strong></span>
            <span className="text-text-muted font-mono text-sm">{result.windows.length} windows</span>
          </div>
          <div className="bg-bg-card rounded-xl border border-white/[0.08] overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-[10px] font-mono font-bold text-text-faint uppercase border-b border-white/[0.06]">
                    <th className="text-left px-4 py-2">Period</th>
                    <th className="text-right px-4 py-2">IS Sharpe</th>
                    <th className="text-right px-4 py-2">OOS Sharpe</th>
                    <th className="text-right px-4 py-2">OOS P&L</th>
                    <th className="text-right px-4 py-2">ATR Mult</th>
                    <th className="text-right px-4 py-2">Max Levels</th>
                  </tr>
                </thead>
                <tbody>
                  {result.windows.map((w) => (
                    <tr key={w.period} className="border-t border-white/[0.04] hover:bg-white/[0.02]">
                      <td className="px-4 py-2 font-mono text-text-faint text-xs">{w.period}</td>
                      <td className="px-4 py-2 font-mono text-right text-text-primary">{w.is_sharpe.toFixed(2)}</td>
                      <td className={`px-4 py-2 font-mono text-right ${w.oos_sharpe >= 0 ? "text-vhe-green" : "text-vhe-red"}`}>{w.oos_sharpe.toFixed(2)}</td>
                      <td className={`px-4 py-2 font-mono text-right ${w.oos_pnl >= 0 ? "text-vhe-green" : "text-vhe-red"}`}>{INR.format(w.oos_pnl)}</td>
                      <td className="px-4 py-2 font-mono text-right text-text-muted">{w.best_params.atr_multiplier}</td>
                      <td className="px-4 py-2 font-mono text-right text-text-muted">{w.best_params.max_levels}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
