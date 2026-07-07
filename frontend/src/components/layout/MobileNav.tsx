import { NavLink } from "react-router-dom";
import { Activity, LayoutDashboard, ShieldAlert, TrendingUp, Zap } from "lucide-react";

const NAV = [
  { label: "Terminal",   to: "/dashboard",            icon: LayoutDashboard },
  { label: "Strategies", to: "/dashboard/strategies", icon: TrendingUp },
  { label: "Execution",  to: "/dashboard/execution",  icon: Zap },
  { label: "Activity",   to: "/dashboard/activity",   icon: Activity },
  { label: "Risk",       to: "/dashboard/risk",       icon: ShieldAlert },
];

export function MobileNav() {
  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 z-40 bg-bg-deep/95 backdrop-blur-xl border-t border-white/[0.08] flex">
      {NAV.map(({ label, to, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/dashboard"}
          className={({ isActive }) =>
            `flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 text-[10px] font-sans font-semibold transition-colors ${
              isActive ? "text-vhe-green" : "text-text-faint hover:text-text-muted"
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Icon className={`w-5 h-5 ${isActive ? "text-vhe-green" : ""}`} />
              <span>{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}
