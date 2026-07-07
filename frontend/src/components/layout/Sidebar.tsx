import { NavLink } from "react-router-dom";
import { Activity, LayoutDashboard, LogOut, ShieldAlert, TrendingUp, User, Zap } from "lucide-react";
import { useAuth } from "../../hooks/useAuth";

const NAV = [
  { label: "Terminal",   to: "/dashboard",            icon: LayoutDashboard },
  { label: "Strategies", to: "/dashboard/strategies", icon: TrendingUp },
  { label: "Execution",  to: "/dashboard/execution",  icon: Zap },
  { label: "Activity",   to: "/dashboard/activity",   icon: Activity },
  { label: "Risk",       to: "/dashboard/risk",       icon: ShieldAlert },
];

export function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="sticky top-0 h-screen w-[220px] flex flex-col gap-6 px-4 py-5 border-r border-vhe-green/[0.08] bg-bg-deep/95 backdrop-blur-xl z-10">
      {/* Logo */}
      <div className="flex items-center gap-3 px-1">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-sm bg-gradient-to-br from-vhe-blue to-vhe-green shadow-lg shadow-vhe-green/20 text-bg-deep">
          V
        </div>
        <div>
          <strong className="block text-[15px] text-text-primary font-sans font-bold leading-tight">VHE</strong>
          <span className="text-text-faint text-[10px] font-mono uppercase tracking-widest">Volatility Engine</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1">
        {NAV.map(({ label, to, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/dashboard"}
            className={({ isActive }) =>
              `relative flex items-center gap-2.5 px-3 py-2.5 rounded-[10px] text-[13px] font-semibold font-sans transition-all duration-150 ${
                isActive
                  ? "text-text-primary bg-vhe-green/[0.10] border border-vhe-green/25"
                  : "text-text-muted border border-transparent hover:text-text-primary hover:bg-white/[0.04]"
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute left-0 inset-y-2 w-0.5 bg-vhe-green rounded-r" />
                )}
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-vhe-green" : ""}`} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User section */}
      {user && (
        <div className="mt-auto flex flex-col gap-2 border-t border-white/[0.06] pt-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-vhe-blue/40 to-vhe-green/40 border border-white/10 flex items-center justify-center">
              <User className="w-3 h-3 text-text-muted" />
            </div>
            <div className="min-w-0">
              <div className="text-[11px] font-mono text-text-muted truncate">{user.name}</div>
              <div className="text-[10px] font-mono text-text-faint truncate">{user.email}</div>
            </div>
          </div>
          <div className="text-[11px] font-mono text-vhe-green px-1">
            ₹{user.virtual_capital_inr.toLocaleString("en-IN")} virtual
          </div>
          <div className="flex items-center justify-between px-1">
            <NavLink
              to="/profile"
              className="text-[12px] font-sans text-text-muted hover:text-text-primary transition-colors"
            >
              Profile →
            </NavLink>
            <button
              onClick={logout}
              className="text-text-faint hover:text-vhe-red transition-colors"
              aria-label="Sign out"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </aside>
  );
}
