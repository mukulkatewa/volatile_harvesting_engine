import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { User } from "../types/api";

export function useAuth() {
  const qc = useQueryClient();
  const { data: user, isLoading } = useQuery<User | null>({
    queryKey: ["me"],
    queryFn: () =>
      api.me().catch((err: unknown) => {
        // Treat 401/404 as logged-out; propagate 5xx so we don't log the user out on server hiccups
        const msg = err instanceof Error ? err.message : "";
        if (msg.includes("503") || msg.includes("500") || msg.includes("network")) throw err;
        return null;
      }),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const logout = async () => {
    await api.logout();
    qc.setQueryData(["me"], null);
    window.location.href = "/";
  };

  return { user: user ?? null, isLoading, logout };
}
