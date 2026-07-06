import { useEffect, useState } from "react";
import type { VHEState } from "../../types/api";

function toIST(date: Date): string {
  return date.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });
}

export function Header({ state }: { state: VHEState }) {
  const [clock, setClock] = useState(toIST(new Date()));
  useEffect(() => {
    const id = setInterval(() => setClock(toIST(new Date())), 1000);
    return () => clearInterval(id);
  }, []);

  const sessionStatus = state.market_session?.status ?? "unknown";
  const sessionCls =
    sessionStatus === "open"
      ? "text-vhe-green border-vhe-green/30 bg-vhe-green/10"
      : sessionStatus === "force_exit"
      ? "text-vhe-red border-vhe-red/30 bg-vhe-red/10"
      : "text-vhe-amber border-vhe-amber/30 bg-vhe-amber/10";

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 border-b border-white/[0.06] bg-bg-deep/90 backdrop-blur-xl">
      <div className="flex items-center gap-4">
        <time className="font-mono text-[18px] font-semibold text-vhe-green">{clock}</time>
        <span className={`text-[11px] font-bold font-mono px-2 py-0.5 rounded border uppercase ${sessionCls}`}>
          {sessionStatus}
        </span>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${state.connected ? "bg-vhe-green animate-pulse" : "bg-vhe-red"}`} />
          <span className="text-[13px] text-text-muted font-sans">
            {state.connected ? "Live" : "Reconnecting"}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3 text-[12px] font-mono text-text-muted">
        <span>Phase <strong className="text-text-primary">{state.phase}</strong></span>
        <span>Mode <strong className="text-text-primary capitalize">{state.mode}</strong></span>
        <span>Feed <strong className="text-text-primary">{state.source}</strong></span>
      </div>
    </header>
  );
}
