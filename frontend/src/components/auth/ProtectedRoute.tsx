import { Navigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";

interface Props {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: Props) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg-deep flex items-center justify-center">
        <span className="font-mono text-text-muted text-sm animate-pulse">Loading…</span>
      </div>
    );
  }

  if (!user) return <Navigate to="/" replace />;
  return <>{children}</>;
}
