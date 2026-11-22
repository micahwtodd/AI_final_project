// Thin typed wrapper over the FastAPI routes. Every number shown in the UI comes from these responses.

export type Action = {
  rate_hedge_pct: number;
  credit_shift_pct: number;
  equity_hedge_pct: number;
  fx_hedge_pct: number;
  cash_buffer_pct: number;
  collateralized: boolean;
  dealers: 1 | 3;
  accept_prt: boolean | null;
};

export type Dashboard = {
  surplus_usd_bn: number;
  assets_usd_bn: number;
  liabilities_usd_bn: number;
  asset_duration_years: number;
  liability_duration_years: number;
  duration_gap_years: number;
  net_dv01_usd_mn: number;
  liquidity_ratio_pct: number;
  capital_ratio_pct: number;
  net_equity_exposure_usd_bn: number;
  fx_exposure_usd_bn: number;
  counterparty_exposure_usd_bn: number;
  derivatives_mtm_usd_bn: number;
  asset_values: Record<string, number>;
  liability_values: Record<string, number>;
  status: Record<string, "green" | "amber" | "red">;
};

export type Company = {
  ticker: string;
  name: string;
  fiscal_year: number;
  invested_assets_usd_bn: number;
  surplus_usd_bn: number;
  equity_to_assets: number;
  asset_mix: Record<string, number>;
  liability_mix: Record<string, number>;
  guarantee_exposure_usd_bn: number;
  separate_account_assets_usd_bn: number;
  dashboard: Dashboard;
};

export type Card = {
  quarter: number;
  title: string;
  era: string;
  signal_text: string;
  offers_prt_deal: boolean;
  glossary_terms: string[];
};

export type HistoryRow = {
  quarter: number;
  title: string;
  surplus_before: number;
  surplus_after: number;
  change: number;
  revealed: boolean;
  score?: number;
};

export type GameView = {
  id: string;
  ticker: string;
  company: string;
  seed: number;
  quarter: number;
  phase: "position" | "explain" | "finished";
  card: Card | null;
  dashboard: Dashboard;
  action: Action;
  pending: Action | null;
  prt_decided: boolean;
  history: HistoryRow[];
  start_surplus_usd_bn: number;
};

export type Preview = {
  before: Dashboard;
  after: Dashboard;
  hedge_cost_per_quarter_usd_bn: number;
  carry_per_quarter_usd_bn: number;
};

export type MarketMove = { key: string; label: string; value: number | null; unit: string };

export type Shock = {
  quarter: number;
  title: string;
  era: string;
  headline: string;
  narrative: string;
  severity: number;
  seed: number;
  market_moves: MarketMove[];
  surplus_before: number;
  surplus_after: number;
  surplus_change: number;
  dashboard_before: Dashboard;
  dashboard_after: Dashboard;
  question: string;
};

export type Reveal = {
  quarter: number;
  attribution: { key: string; label: string; value: number }[];
  total: number;
  comparison: { you: number; nothing: number; benchmark: number };
  quarter_score: number;
  debrief_text: string[];
  lesson: string;
  benchmark_action: Partial<Action>;
  your_action: Partial<Action>;
  source_note: string;
  finished: boolean;
  view: GameView;
};

export type Debrief = {
  results_score: number;
  per_quarter: number[];
  penalties: number;
  start_surplus: number;
  end_surplus: number;
  nothing_end_surplus: number;
  benchmark_end_surplus: number;
  text: string[];
  lessons: { quarter: number; title: string; lesson: string }[];
  minutes_played: number;
  history: HistoryRow[];
};

export type Health = { ok: boolean; key_found: boolean; provider: string | null; model: string };

async function call<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `${res.status}`;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* keep status */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<Health>("/health"),
  companies: () => call<Company[]>("/companies"),
  newGame: (ticker: string, seed: number) => call<GameView>("/game", { ticker, seed }),
  game: (id: string) => call<GameView>(`/game/${id}`),
  preview: (id: string, action: Action) => call<Preview>(`/game/${id}/preview`, { action }),
  commit: (id: string, actions: Action) => call<{ view: GameView; after: Dashboard }>(`/game/${id}/commit`, { actions }),
  advance: (id: string) => call<Shock>(`/game/${id}/advance`, {}),
  explain: (id: string, text: string, not_sure: boolean) => call<Reveal>(`/game/${id}/explain`, { text, not_sure }),
  debrief: (id: string) => call<Debrief>(`/game/${id}/debrief`),
};
