import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import type { User } from "../types/api";

export function useAuth() {
  const qc = useQueryClient();
  const { data: user, isLoading } = useQuery<User | null>({
    queryKey: ["me"],
    queryFn: () => api.me().catch(() => null),
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
