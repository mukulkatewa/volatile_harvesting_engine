import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../hooks/useAuth";
import { api } from "../../api/client";
import { useWebSocket } from "../../hooks/useWebSocket";

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function ProfilePage() {
  const { user, logout } = useAuth();
  const { state } = useWebSocket();
  const qc = useQueryClient();
  const [capital, setCapital] = useState(user?.virtual_capital_inr ?? 75000);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!user) return null;

  const equity = state.portfolio?.equity ?? 0;
  const initialEngineCapital = 75000;
  const sessionPnlPct = initialEngineCapital > 0 ? (equity - initialEngineCapital) / initialEngineCapital : 0;
  const userEquity = user.virtual_capital_inr * (1 + sessionPnlPct);
  const userPnl = userEquity - user.virtual_capital_inr;

  const saveCapital = async () => {
    if (capital < 25000 || capital > 500000) { setErr("Must be between ₹25,000 and ₹5,00,000"); return; }
    setErr(null); setSaving(true);
    try {
      const updated = await api.updateCapital(capital);
      qc.setQueryData(["me"], updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally { setSaving(false); }
  };

  return (
    <div className="min-h-screen bg-bg-deep p-8">
      <div className="max-w-lg mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-vhe-blue to-vhe-green flex items-center justify-center text-lg font-bold">
            {user.name[0]?.toUpperCase() ?? "U"}
          </div>
          <div>
            <h1 className="text-xl font-bold font-sans text-text-primary">{user.name}</h1>
            <p className="text-text-muted font-mono text-sm">{user.email}</p>
          </div>
        </div>

        <div className="bg-bg-card rounded-xl border border-white/[0.08] p-5 space-y-4">
          <h2 className="text-sm font-bold font-sans text-text-muted uppercase tracking-wider">Virtual Portfolio</h2>
          <div className="grid grid-cols-2 gap-4">
            {[
              { label: "Starting Capital", value: INR.format(user.virtual_capital_inr), cls: "text-text-primary" },
              { label: "Current Value",    value: INR.format(userEquity),               cls: "text-vhe-green" },
              { label: "Session P&L",      value: INR.format(userPnl),                  cls: userPnl >= 0 ? "text-vhe-green" : "text-vhe-red" },
              { label: "Return %",         value: `${(sessionPnlPct * 100).toFixed(2)}%`, cls: sessionPnlPct >= 0 ? "text-vhe-green" : "text-vhe-red" },
            ].map(({ label, value, cls }) => (
              <div key={label}>
                <div className="text-[10px] font-mono text-text-faint uppercase tracking-wider">{label}</div>
                <div className={`text-xl font-mono font-semibold mt-1 ${cls}`}>{value}</div>
              </div>
            ))}
          </div>
          <p className="text-text-faint font-mono text-xs">Based on shared session P&L. All users see the same live engine positions.</p>
        </div>

        <div className="bg-bg-card rounded-xl border border-white/[0.08] p-5 space-y-4">
          <h2 className="text-sm font-bold font-sans text-text-muted uppercase tracking-wider">Adjust Virtual Capital</h2>
          <div className="flex gap-2">
            <input type="number" value={capital} onChange={(e) => setCapital(Number(e.target.value))}
              min={25000} max={500000} step={5000}
              className="flex-1 bg-bg-elevated border border-white/15 text-text-primary font-mono text-sm px-3 py-2 rounded-lg" />
            <button onClick={saveCapital} disabled={saving}
              className="px-4 py-2 rounded-lg bg-vhe-green/10 border border-vhe-green/30 text-vhe-green text-sm font-semibold font-sans hover:bg-vhe-green/20 disabled:opacity-50 transition-colors">
              {saving ? "Saving…" : saved ? "Saved ✓" : "Save"}
            </button>
          </div>
          {err && <p className="text-vhe-red font-mono text-xs">{err}</p>}
          <p className="text-text-faint font-mono text-xs">Range: ₹25,000 – ₹5,00,000</p>
        </div>

        <div className="flex justify-between items-center pt-2">
          <a href="/dashboard" className="text-sm text-vhe-blue font-sans hover:underline">← Back to Dashboard</a>
          <button onClick={logout} className="text-sm text-text-faint font-sans hover:text-vhe-red transition-colors">Sign out</button>
        </div>
      </div>
    </div>
  );
}
