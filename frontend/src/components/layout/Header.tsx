import { useEffect, useState } from "react";
import { Bell, Settings, Wifi, WifiOff } from "lucide-react";
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
      ? "text-vhe-green border-vhe-green/30 bg-vhe-green/[0.08]"
      : sessionStatus === "force_exit"
      ? "text-vhe-red border-vhe-red/30 bg-vhe-red/[0.08]"
      : "text-vhe-amber border-vhe-amber/30 bg-vhe-amber/[0.08]";

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between px-6 py-3 border-b border-white/[0.06] bg-bg-deep/90 backdrop-blur-xl">
      <div className="flex items-center gap-4">
        <time className="font-mono text-[17px] font-semibold text-vhe-green tabular-nums">{clock}</time>

        <span className={`text-[10px] font-bold font-mono px-3 py-1 rounded-full border uppercase tracking-wide ${sessionCls}`}>
          {sessionStatus}
        </span>

        <div className="flex items-center gap-1.5">
          {state.connected ? (
            <Wifi className="w-3.5 h-3.5 text-vhe-green" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-vhe-red" />
          )}
          <span className={`text-[12px] font-sans ${state.connected ? "text-text-muted" : "text-vhe-red"}`}>
            {state.connected ? "Live" : "Reconnecting"}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="hidden sm:flex items-center gap-3 text-[12px] font-mono text-text-muted">
          <span>Phase <strong className="text-text-primary">{state.phase}</strong></span>
          <span className="text-white/20">·</span>
          <span>Mode <strong className="text-text-primary capitalize">{state.mode}</strong></span>
          <span className="text-white/20">·</span>
          <span>Feed <strong className="text-text-primary">{state.source}</strong></span>
        </div>

        <div className="flex items-center gap-2 border-l border-white/[0.08] pl-4">
          <button
            className="p-1.5 rounded-lg text-text-faint hover:text-text-muted hover:bg-white/[0.04] transition-all"
            aria-label="Notifications"
          >
            <Bell className="w-4 h-4" />
          </button>
          <button
            className="p-1.5 rounded-lg text-text-faint hover:text-text-muted hover:bg-white/[0.04] transition-all"
            aria-label="Settings"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
}
