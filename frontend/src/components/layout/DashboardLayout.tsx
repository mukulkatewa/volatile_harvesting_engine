import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import { useWebSocket } from "../../hooks/useWebSocket";
import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { Header } from "./Header";
import { Terminal } from "../dashboard/Terminal";
import { Strategies } from "../dashboard/Strategies";
import { Execution } from "../dashboard/Execution";
import { Activity } from "../dashboard/Activity";
import { RiskTab } from "../risk/RiskTab";

export function DashboardLayout() {
  const { state, postControl } = useWebSocket();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-bg-deep">
      {/* Desktop sidebar */}
      <div className="hidden lg:block">
        <Sidebar />
      </div>

      {/* Mobile sidebar drawer */}
      {sidebarOpen && (
        <>
          <div
            className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="fixed inset-y-0 left-0 z-30 lg:hidden">
            <Sidebar onClose={() => setSidebarOpen(false)} />
          </div>
        </>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header state={state} onMenuOpen={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-y-auto pb-20 lg:pb-0">
          <Routes>
            <Route index element={<Terminal state={state} postControl={postControl} />} />
            <Route path="strategies" element={<Strategies state={state} />} />
            <Route path="execution" element={<Execution state={state} postControl={postControl} />} />
            <Route path="activity" element={<Activity state={state} />} />
            <Route path="risk" element={<RiskTab />} />
          </Routes>
        </main>
      </div>

      {/* Mobile bottom navigation */}
      <MobileNav />
    </div>
  );
}
