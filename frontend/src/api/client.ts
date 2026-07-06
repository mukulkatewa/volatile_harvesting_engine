import type { MonteCarloResult, User, VHEState, WFResult } from "../types/api";

async function fetchJSON<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const resp = await fetch(input, init);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error((body as { detail?: string }).detail ?? resp.statusText);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  state: () => fetchJSON<VHEState>("/api/state"),
  me: () => fetchJSON<User>("/api/me"),
  updateCapital: (capital: number) =>
    fetchJSON<User>("/api/me/capital", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ virtual_capital_inr: capital }),
    }),
  logout: () => fetchJSON<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  runMonteCarlo: (payload: {
    symbol: string;
    bars_file: string;
    n_sims: number;
    initial_capital: number;
  }) =>
    fetchJSON<MonteCarloResult>("/api/backtest/monte-carlo", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  runWalkForward: (params: {
    symbol: string;
    bars_file: string;
    train_days: number;
    test_days: number;
  }) => {
    const qs = new URLSearchParams(params as unknown as Record<string, string>);
    return fetchJSON<WFResult>(`/api/backtest/walk-forward?${qs}`);
  },
};
