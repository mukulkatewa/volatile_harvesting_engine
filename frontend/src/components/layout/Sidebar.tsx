import { NavLink } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

const NAV = [
  { label: "Terminal",   to: "/dashboard" },
  { label: "Strategies", to: "/dashboard/strategies" },
  { label: "Execution",  to: "/dashboard/execution" },
  { label: "Activity",   to: "/dashboard/activity" },
  { label: "Risk",       to: "/dashboard/risk" },
];

export function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="sticky top-0 h-screen w-[220px] flex flex-col gap-6 px-4 py-5 border-r border-white/[0.08] bg-bg-deep/95 backdrop-blur-xl z-10">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center font-bold text-base bg-gradient-to-br from-vhe-blue to-vhe-green shadow-lg">
          V
        </div>
        <div>
          <strong className="block text-[15px] text-text-primary font-sans font-bold">VHE</strong>
          <span className="text-text-muted text-[11px] font-sans uppercase tracking-widest">Volatility Engine</span>
        </div>
      </div>

      <nav className="flex flex-col gap-1.5">
        {NAV.map(({ label, to }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/dashboard"}
            className={({ isActive }) =>
              `px-3 py-2.5 rounded-[10px] text-[13px] font-semibold font-sans transition-all duration-150 ${
                isActive
                  ? "text-text-primary bg-vhe-blue/16 border border-vhe-blue/35"
                  : "text-text-muted border border-transparent hover:text-text-primary hover:bg-white/[0.03]"
              }`
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {user && (
        <div className="mt-auto flex flex-col gap-2">
          <div className="text-[11px] font-mono text-text-faint truncate">{user.email}</div>
          <div className="text-[11px] font-mono text-vhe-green">
            ₹{user.virtual_capital_inr.toLocaleString("en-IN")} virtual
          </div>
          <NavLink
            to="/profile"
            className="text-[12px] font-sans text-text-muted hover:text-text-primary transition-colors"
          >
            Profile →
          </NavLink>
          <button
            onClick={logout}
            className="text-left text-[12px] font-sans text-text-faint hover:text-vhe-red transition-colors"
          >
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
