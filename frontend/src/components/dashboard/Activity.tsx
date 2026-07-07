import type { VHEState } from "../../types/api";

export function Activity({ state }: { state: VHEState }) {
  const events = [...(state.events ?? [])].reverse().slice(0, 50);
  const SEV: Record<string, string> = {
    info: "text-text-muted",
    warning: "text-vhe-amber",
    danger: "text-vhe-red",
    success: "text-vhe-green",
  };
  return (
    <div className="p-3 sm:p-6 space-y-6">
      <h2 className="text-lg font-bold font-sans text-text-primary">Event Log</h2>
      {events.length === 0 ? (
        <p className="text-text-muted font-mono text-sm">No events yet.</p>
      ) : (
        <div className="bg-bg-card rounded-xl border border-white/[0.08] divide-y divide-white/[0.04]">
          {events.map((ev) => (
            <div key={`${ev.timestamp}-${ev.message}`} className="px-4 py-2.5 flex items-start gap-3">
              <span className="font-mono text-[10px] text-text-faint pt-0.5 shrink-0">
                {new Date(ev.timestamp).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false })}
              </span>
              <span className={`text-xs font-mono uppercase font-bold w-16 shrink-0 ${SEV[ev.severity] ?? "text-text-muted"}`}>
                {ev.category}
              </span>
              <span className="text-sm font-sans text-text-primary">{ev.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
