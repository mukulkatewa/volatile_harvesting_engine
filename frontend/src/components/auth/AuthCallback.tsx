import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";

export function AuthCallback() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  useEffect(() => {
    api
      .me()
      .then((user) => {
        qc.setQueryData(["me"], user);
        navigate("/dashboard", { replace: true });
      })
      .catch(() => navigate("/?error=session_failed", { replace: true }));
  }, [navigate, qc]);

  return (
    <div className="min-h-screen bg-bg-deep flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-vhe-blue to-vhe-green animate-pulse" />
        <span className="font-mono text-text-muted text-sm">Signing you in…</span>
      </div>
    </div>
  );
}
