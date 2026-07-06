import { lazy, Suspense } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { LandingPage } from "./components/auth/LandingPage";
import { AuthCallback } from "./components/auth/AuthCallback";
import { ProtectedRoute } from "./components/auth/ProtectedRoute";
import { DashboardLayout } from "./components/layout/DashboardLayout";

const LazyProfile = lazy(() =>
  import("./components/profile/ProfilePage").then((m) => ({ default: m.ProfilePage }))
);

function Fallback() {
  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <span className="font-mono text-text-muted text-sm animate-pulse">Loading…</span>
    </div>
  );
}

const qc = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route
            path="/dashboard/*"
            element={
              <ProtectedRoute>
                <DashboardLayout />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <Suspense fallback={<Fallback />}>
                  <LazyProfile />
                </Suspense>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
