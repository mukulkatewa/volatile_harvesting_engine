import { Route, Routes } from "react-router-dom";
import { useWebSocket } from "../../hooks/useWebSocket";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { Terminal } from "../dashboard/Terminal";
import { Strategies } from "../dashboard/Strategies";
import { Execution } from "../dashboard/Execution";
import { Activity } from "../dashboard/Activity";
import { RiskTab } from "../risk/RiskTab";

export function DashboardLayout() {
  const { state, postControl } = useWebSocket();

  return (
    <div className="flex min-h-screen bg-bg-deep">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header state={state} />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route index element={<Terminal state={state} postControl={postControl} />} />
            <Route path="strategies" element={<Strategies state={state} />} />
            <Route path="execution" element={<Execution state={state} postControl={postControl} />} />
            <Route path="activity" element={<Activity state={state} />} />
            <Route path="risk" element={<RiskTab />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
