export interface Quote {
  symbol: string;
  ltp: number;
  timestamp: string;
  stale?: boolean;
}

export interface Portfolio {
  cash: number;
  equity: number;
  gross_exposure: number;
  gross_exposure_pct: number;
  positions: Record<string, { quantity: number; avg_price: number; unrealized_pnl: number }>;
}

export interface Controls {
  kill_switch: boolean;
  automation_paused: boolean;
  last_risk_reject: string | null;
  kill_switch_reason: string | null;
}

export interface GridPlan {
  symbol: string;
  regime: string;
  fair_value: number;
  current_price: number;
  levels_filled: number;
  total_levels: number;
}

export interface Fill {
  fill_id: string;
  symbol: string;
  side: "BUY" | "SELL";
  price: number;
  quantity: number;
  fees: number;
  reason: string;
  filled_at: string;
}

export interface VHEState {
  connected: boolean;
  mode: string;
  source: string;
  phase: number | string;
  server_time: string;
  portfolio: Portfolio;
  controls: Controls;
  quotes: Record<string, Quote>;
  plans: Record<string, GridPlan>;
  fills: Fill[];
  events: Array<{ category: string; message: string; severity: string; timestamp: string }>;
  capital?: Record<string, number>;
  market_session?: { status: string };
  strategy_status?: Record<string, unknown>;
  sentiment?: Record<string, unknown>;
}

export interface User {
  id: number;
  email: string;
  name: string;
  virtual_capital_inr: number;
  created_at: string;
}

export interface MonteCarloResult {
  var_95: number;
  cvar_95: number;
  p_ruin: number;
  drawdown_p95: number;
  kelly_fraction: number;
  pnl_percentiles: { p5: number; p25: number; p50: number; p75: number; p95: number };
  equity_curves: number[][];
  sim_count: number;
  trade_count: number;
}

export interface WFWindow {
  period: string;
  is_sharpe: number;
  oos_sharpe: number;
  oos_pnl: number;
  best_params: { atr_multiplier: number; max_levels: number };
}

export interface WFResult {
  windows: WFWindow[];
  wf_efficiency: number;
  verdict: "Not overfit" | "Marginal" | "Curve-fitted";
  param_stability: { atr_multiplier: number; stability_score: number };
}
