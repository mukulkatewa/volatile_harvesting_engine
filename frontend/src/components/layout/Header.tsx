import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, Menu, Settings, User, LogOut, Wifi, WifiOff, ChevronRight, X } from "lucide-react";
import type { VHEState } from "../../types/api";
import { useAuth } from "../../hooks/useAuth";

function toIST(date: Date): string {
  return date.toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });
}

const SEV_CLS: Record<string, string> = {
  danger:  "text-vhe-red",
  warning: "text-vhe-amber",
  success: "text-vhe-green",
  info:    "text-text-muted",
};

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function Header({ state, onMenuOpen }: { state: VHEState; onMenuOpen?: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [clock, setClock] = useState(toIST(new Date()));
  const [notifOpen, setNotifOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [seenCount, setSeenCount] = useState(state.events?.length ?? 0);

  const notifRef = useRef<HTMLDivElement>(null);
  const settingsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = setInterval(() => setClock(toIST(new Date())), 1000);
    return () => clearInterval(id);
  }, []);

  // Close dropdowns on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setNotifOpen(false);
      if (settingsRef.current && !settingsRef.current.contains(e.target as Node)) setSettingsOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const events = state.events ?? [];
  const unread = Math.max(0, events.length - seenCount);

  function openNotif() {
    setNotifOpen((o) => !o);
    setSettingsOpen(false);
    setSeenCount(events.length);
  }

  function openSettings() {
    setSettingsOpen((o) => !o);
    setNotifOpen(false);
  }

  const sessionStatus = state.market_session?.status ?? "unknown";
  const sessionCls =
    sessionStatus === "open"
      ? "text-vhe-green border-vhe-green/30 bg-vhe-green/[0.08]"
      : sessionStatus === "force_exit"
      ? "text-vhe-red border-vhe-red/30 bg-vhe-red/[0.08]"
      : "text-vhe-amber border-vhe-amber/30 bg-vhe-amber/[0.08]";

  const recentEvents = [...events].reverse().slice(0, 15);

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between px-3 sm:px-6 py-3 border-b border-white/[0.06] bg-bg-deep/90 backdrop-blur-xl">
      {/* Left: hamburger (mobile) + clock + session status + connection */}
      <div className="flex items-center gap-3">
        {onMenuOpen && (
          <button
            onClick={onMenuOpen}
            className="lg:hidden p-1.5 rounded-lg text-text-faint hover:text-text-primary hover:bg-white/[0.06] transition-all"
            aria-label="Open menu"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <time className="font-mono text-[15px] sm:text-[17px] font-semibold text-vhe-green tabular-nums">{clock}</time>

        <span className={`hidden sm:inline text-[10px] font-bold font-mono px-3 py-1 rounded-full border uppercase tracking-wide ${sessionCls}`}>
          {sessionStatus}
        </span>

        <div className="flex items-center gap-1.5">
          {state.connected ? (
            <Wifi className="w-3.5 h-3.5 text-vhe-green" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-vhe-red" />
          )}
          <span className={`hidden sm:inline text-[12px] font-sans ${state.connected ? "text-text-muted" : "text-vhe-red"}`}>
            {state.connected ? "Live" : "Reconnecting"}
          </span>
        </div>
      </div>

      {/* Right: meta info + bell + settings */}
      <div className="flex items-center gap-4">
        <div className="hidden sm:flex items-center gap-3 text-[12px] font-mono text-text-muted">
          <span>Phase <strong className="text-text-primary">{state.phase}</strong></span>
          <span className="text-white/20">·</span>
          <span>Mode <strong className="text-text-primary capitalize">{state.mode}</strong></span>
          <span className="text-white/20">·</span>
          <span>Feed <strong className="text-text-primary">{state.source}</strong></span>
        </div>

        <div className="flex items-center gap-2 border-l border-white/[0.08] pl-4">

          {/* ── Bell / Notifications ── */}
          <div ref={notifRef} className="relative">
            <button
              onClick={openNotif}
              className="relative p-1.5 rounded-lg text-text-faint hover:text-text-primary hover:bg-white/[0.06] transition-all"
              aria-label="Notifications"
            >
              <Bell className="w-4 h-4" />
              {unread > 0 && (
                <span className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-0.5 rounded-full bg-vhe-red text-[9px] font-bold font-mono text-white flex items-center justify-center leading-none">
                  {unread > 99 ? "99+" : unread}
                </span>
              )}
            </button>

            {notifOpen && (
              <div className="absolute right-0 top-10 w-80 bg-bg-panel border border-white/[0.10] rounded-xl shadow-2xl shadow-black/40 overflow-hidden">
                <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.07]">
                  <span className="text-[12px] font-bold font-sans text-text-primary">Notifications</span>
                  <button onClick={() => setNotifOpen(false)} className="text-text-faint hover:text-text-muted">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>

                {recentEvents.length === 0 ? (
                  <div className="px-4 py-8 text-center text-text-faint font-mono text-xs">No events yet</div>
                ) : (
                  <div className="max-h-80 overflow-y-auto divide-y divide-white/[0.04]">
                    {recentEvents.map((ev, i) => (
                      <div key={`${ev.timestamp}-${i}`} className="px-4 py-2.5 flex items-start gap-3 hover:bg-white/[0.02] transition-colors">
                        <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${
                          ev.severity === "danger"  ? "bg-vhe-red" :
                          ev.severity === "warning" ? "bg-vhe-amber" :
                          ev.severity === "success" ? "bg-vhe-green" :
                          "bg-text-faint"
                        }`} />
                        <div className="min-w-0 flex-1">
                          <div className="text-[11px] font-sans text-text-primary leading-snug">{ev.message}</div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className={`text-[9px] font-mono font-bold uppercase ${SEV_CLS[ev.severity] ?? "text-text-faint"}`}>
                              {ev.category}
                            </span>
                            <span className="text-[9px] font-mono text-text-faint">
                              {new Date(ev.timestamp).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="px-4 py-2.5 border-t border-white/[0.07]">
                  <button
                    onClick={() => { setNotifOpen(false); navigate("/dashboard/activity"); }}
                    className="text-[11px] font-sans text-vhe-green hover:text-vhe-green/80 transition-colors flex items-center gap-1"
                  >
                    View full event log <ChevronRight className="w-3 h-3" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* ── Settings ── */}
          <div ref={settingsRef} className="relative">
            <button
              onClick={openSettings}
              className="p-1.5 rounded-lg text-text-faint hover:text-text-primary hover:bg-white/[0.06] transition-all"
              aria-label="Settings"
            >
              <Settings className="w-4 h-4" />
            </button>

            {settingsOpen && (
              <div className="absolute right-0 top-10 w-64 bg-bg-panel border border-white/[0.10] rounded-xl shadow-2xl shadow-black/40 overflow-hidden">
                <div className="px-4 py-3 border-b border-white/[0.07]">
                  <div className="text-[12px] font-bold font-sans text-text-primary">Settings</div>
                </div>

                {/* User info */}
                {user && (
                  <div className="px-4 py-3 border-b border-white/[0.07] flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-vhe-blue/40 to-vhe-green/40 border border-white/10 flex items-center justify-center shrink-0">
                      <User className="w-4 h-4 text-text-muted" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-[12px] font-sans text-text-primary truncate font-semibold">{user.name}</div>
                      <div className="text-[10px] font-mono text-text-faint truncate">{user.email}</div>
                    </div>
                  </div>
                )}

                {/* Capital */}
                {user && (
                  <div className="px-4 py-2.5 border-b border-white/[0.07]">
                    <div className="text-[10px] font-mono text-text-faint uppercase tracking-wide mb-1">Virtual Capital</div>
                    <div className="text-[15px] font-mono font-semibold text-vhe-green">{INR.format(user.virtual_capital_inr)}</div>
                    <div className="text-[10px] font-mono text-text-faint mt-0.5">
                      Mode: <span className="text-text-muted capitalize">{state.mode}</span>
                      {" · "}Feed: <span className="text-text-muted">{state.source}</span>
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="py-1.5">
                  <button
                    onClick={() => { setSettingsOpen(false); navigate("/profile"); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-[12px] font-sans text-text-muted hover:text-text-primary hover:bg-white/[0.04] transition-colors text-left"
                  >
                    <User className="w-3.5 h-3.5 shrink-0" />
                    Profile & Capital Settings
                    <ChevronRight className="w-3.5 h-3.5 ml-auto" />
                  </button>

                  <button
                    onClick={() => { setSettingsOpen(false); logout(); }}
                    className="w-full flex items-center gap-3 px-4 py-2.5 text-[12px] font-sans text-text-muted hover:text-vhe-red hover:bg-vhe-red/[0.05] transition-colors text-left"
                  >
                    <LogOut className="w-3.5 h-3.5 shrink-0" />
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>

        </div>
      </div>
    </header>
  );
}
