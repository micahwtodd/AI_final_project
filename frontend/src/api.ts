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
  collateral_posted_usd_bn?: number;
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
  accession: string;
  foreign_share: number;
  dossier: DossierRow[];
  reference: Record<string, { value: number; source: string; citation: string; note: string }>;
  rejections: { field: string; reason: string; quote?: string }[];
  sanitizer: { hidden_elements?: number; comments?: number; zero_width_chars?: number; chunks?: number; quarantined?: number };
  dashboard: Dashboard;
  inputs: GameInput[];
};

export type GameInput = { key: string; label: string; unit: "bn" | "pct" | "x"; min: number; max: number; value: number; group: string };

export type DossierRow = {
  key: string; label: string; unit: "bn" | "pct"; value: number;
  source: "tagged" | "filing_text" | "assumption" | "derived"; citation: string; note: string;
};

export type Card = {
  quarter: number;
  title: string;
  era: string;
  signal_text: string;
  offers_prt_deal: boolean;
  boss?: boolean;
  rule?: string | null;
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

export type Badge = { id: string; quarter: number; name: string; icon: string; text: string };
export type Achievements = { earned: Badge[]; streaks: { floor: number; explain: number }; available: number };
export type ReportCard = { grade: string; overall: number; title: string; why: string; breaches: number; avg_hedge_pct: number; breach_detail?: string[];
  weights: { results: number; understanding: number } };

export type GameView = {
  id: string;
  ticker: string;
  company: string;
  seed: number;
  demo: boolean;
  agent_mode: AgentMode;
  quarter: number;
  phase: "position" | "explain" | "finished";
  card: Card | null;
  dashboard: Dashboard;
  action: Action;
  pending: Action | null;
  prt_decided: boolean;
  history: HistoryRow[];
  start_surplus_usd_bn: number;
  usage: Usage;
  chat: ChatMsg[];
  quiz_taken: string[];
  custom_inputs: string[];
  achievements: Achievements;
  n_quarters: number;
  collapsed: boolean;
  unlocked?: string[];
  new_unlocks?: string[];
};

export type Usage = {
  spend_usd: number;
  budget_cap_usd: number;
  blocked: boolean;
  tokens: { input: number; cached: number; cache_write: number; output: number; reasoning: number; requests: number };
  by_agent: Record<string, { input: number; cached: number; output: number; requests: number; cost_usd: number }>;
};

export type Ticket = { action: Action; rationale: string; by: string };

export type ChatMsg = {
  role: "user" | "agent";
  text: string;
  agent?: string;
  agent_name?: string;
  run_id?: string;
  stopped?: string | null;
  proposed_ticket?: Ticket | null;
  subs?: SubAnswer[];
  quarter?: number;
};

export type SubAnswer = { agent: string; agent_name: string; text: string };
export type AgentMode = "solo" | "team";
export type Colleague = "team" | "actuary" | "portfolio_manager" | "trader";

export type AgentEvent = {
  ts: number;
  run_id: string;
  agent: string;
  agent_name?: string;
  type: "start" | "delegation" | "tool_call" | "tool_result" | "reply" | "blocked" | "spend" | "stop" | "error" | "usage";
  detail: any; // eslint-disable-line @typescript-eslint/no-explicit-any
  input_tokens: number;
  cached_tokens: number;
  output_tokens: number;
  cost_usd: number;
};

export type Preview = {
  before: Dashboard;
  after: Dashboard;
  hedge_cost_per_quarter_usd_bn: number;
  carry_per_quarter_usd_bn: number;
};

export type MarketMove = { key: string; label: string; value: number | null; unit: string };

export type Shock = {
  real_world?: { title: string; text: string };
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
  sample_answer: string | null;
  boss?: boolean;
  collapsed?: boolean;
  nothing_collapsed?: boolean;
  prediction?: { pick: string; answer: string; correct: boolean; pick_label: string; answer_label: string; reason?: string } | null;
};

export type Reveal = {
  quarter: number;
  badges_new: Badge[];
  attribution: { key: string; label: string; value: number }[];
  total: number;
  comparison: { you: number; nothing: number; benchmark: number };
  collapsed?: { you: boolean; nothing: boolean; benchmark: boolean };
  lever_gains?: Record<string, number>;
  lever_effects?: Record<string, number>;
  next_is_boss?: boolean;
  title?: string;
  boss?: boolean;
  n_quarters?: number;
  surplus_before?: number;
  quarter_score: number;
  debrief_text: string[];
  lesson: string;
  benchmark_action: Partial<Action>;
  your_action: Partial<Action>;
  source_note: string;
  improvement_facts: string[];
  main_driver: string;
  second_factor: string;
  review: Review | null;
  marker: "ai" | "keywords" | null;
  not_sure: boolean;
  attempts: { text: string; checks: Checks }[];
  understanding: { points: number; by_check: Record<string, number>; not_sure: boolean; attempts: number } | null;
  finished: boolean;
  view: GameView;
};

export type Checks = { main_driver: boolean; mechanism: boolean; second_factor: boolean; improvement: boolean };
export type Review = { checks: Checks; misconceptions: string[]; follow_up: string | null; reply_text: string; instruction_attempt: boolean };
export type ExplainResult =
  | ({ final: true } & Reveal)
  | { final: false; attempt: number; review: Review; marker: string; question: string };

export type Debrief = {
  achievements: Achievements;
  badge_catalog: Omit<Badge, "quarter">[];
  report_card: ReportCard;
  understanding_score: number;
  understanding_per_quarter: Record<string, number>;
  results_score: number;
  per_quarter: number[];
  penalties: number;
  start_surplus: number;
  end_surplus: number;
  nothing_end_surplus: number;
  benchmark_end_surplus: number;
  collapsed?: boolean;
  n_quarters?: number;
  try_next?: string | null;
  verdict?: string;
  paths?: { you: number[]; nothing: number[]; pro: number[] };
  quarters?: { quarter: number; title: string; takeaway: string; you: number; nothing: number; pro: number; results: number; beat_pro: boolean;
    explain: number; not_sure: boolean; breaches: string[]; collapsed: boolean; try_next: string | null; called: boolean | null }[];
  skills?: { concept: string; quarter: number; level: "got_it" | "getting_there" | "revisit"; named_driver: boolean; explained_why: boolean;
    quiz: boolean | null; quiz_when: "before" | "after" | null }[];
  harder?: { ticker: string; name: string; cushion_pct: number } | null;
  predictions?: { made: number; correct: number };
  text: string[];
  lessons: { quarter: number; title: string; lesson: string }[];
  minutes_played: number;
  history: HistoryRow[];
  before_after: BeforeAfter;
};

export type WhatIf = { quarter: number; change: number; surplus_after: number; actual_change: number; nothing_change: number;
  pro_change: number; collapsed: boolean; start_action: Action; locked: string[] };

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
  checkQuiz: (id: string, when: "pre" | "post", qid: string, choice: string) =>
    call<{ id: string; choice: string; correct: boolean; answer: string; explain: string }>(`/quiz/${id}/${when}/check`, { qid, choice }),
  newGame: (ticker: string, seed: number, demo = false, overrides: Record<string, number> = {}) =>
    call<GameView>("/game", { ticker, seed, demo, agent_mode: "team", overrides }),
  previewCompany: (ticker: string, overrides: Record<string, number>) =>
    call<{ dashboard: Dashboard; inputs: GameInput[] }>(`/companies/${ticker}/preview`, { overrides }),
  game: (id: string) => call<GameView>(`/game/${id}`),
  preview: (id: string, action: Action) => call<Preview>(`/game/${id}/preview`, { action }),
  commit: (id: string, actions: Action) => call<{ view: GameView; after: Dashboard }>(`/game/${id}/commit`, { actions }),
  advance: (id: string, prediction?: string | null) => call<Shock>(`/game/${id}/advance`, { prediction: prediction ?? null }),
  whatif: (id: string, action: Partial<Action>) => call<WhatIf>(`/game/${id}/whatif`, { action }),
  hint: (id: string) => call<{ level: number; max: number; hint: string }>(`/game/${id}/hint`, {}),
  explain: (id: string, text: string, not_sure: boolean) => call<ExplainResult>(`/game/${id}/explain`, { text, not_sure }),
  debrief: (id: string) => call<Debrief>(`/game/${id}/debrief`),
  usage: (id: string) => call<Usage>(`/usage/${id}`),
  setBudget: (id: string, cap_usd: number) => call<Usage>(`/budget/${id}`, { cap_usd }),
  setMode: (id: string, agent_mode: AgentMode) => call<{ agent_mode: AgentMode }>(`/game/${id}/mode`, { agent_mode }),
  quizForm: (when: "pre" | "post") => call<QuizForm>(`/quiz/${when}`),
  submitQuiz: (id: string, when: "pre" | "post", answers: Record<string, string>, confidence: Record<string, number>) =>
    call<QuizResult>(`/quiz/${id}/${when}`, { answers, confidence }),
  feedback: (id: string, text: string) => call<{ ok: boolean }>(`/game/${id}/feedback`, { text }),
  summary: (id: string) => call<Record<string, unknown>>(`/game/${id}/summary`),
  flag: (event_id: string, session_id: string, note: string, text: string) => call<{ ok: boolean }>("/flag", { event_id, session_id, note, text }),
  safety: () => call<SafetyLab>("/safety"),
  runSafety: () => call<SafetyLab>("/safety/run", {}),
};

export type QuizForm = {
  when: "pre" | "post"; form: string;
  questions: { id: string; concept: string; q: string; options: Record<string, string> }[];
  confidence: { id: string; text: string }[];
};
export type QuizResult = { when: string; correct: number; total: number; score: number; by_concept: Record<string, boolean>;
  confidence_avg: number; answers_key: Record<string, string> | null };
export type BeforeAfter = {
  quiz_pre: { correct: number; total: number; score: number } | null;
  quiz_post: { correct: number; total: number; score: number } | null;
  quiz_change_pts: number | null; confidence_pre_avg: number | null; confidence_post_avg: number | null; confidence_change: number | null;
  concepts: { concept: string; pre: boolean | null; post: boolean | null }[];
  confidence_items: { id: string; text: string; pre: number | null; post: number | null }[];
  minutes_played: number;
};

export type SafetyOutcome = { outcome: string; detail: string; input_tokens: number; cached_tokens: number; output_tokens: number; cost_usd: number };
export type SafetyLab = {
  generated: string | null;
  seconds?: number;
  total_cost_usd?: number;
  attacks?: { rows: { id: string; label: string; kind: string; off: SafetyOutcome | null; on: SafetyOutcome; layers: string[]; extra_cost_usd: number }[];
    attacks_blocked: number; attacks_total: number; clean_passed: number; clean_total: number };
  teaching?: { rows: { id: string; agent: string; concept: string; question: string; expected: string; answer: string | null; correct: boolean; reason: string }[];
    correct: number; total: number; pass_rate: number; cost_usd: number };
  examiner?: { rows: { id: string; kind: string; text: string; expected: Record<string, boolean>; got: Record<string, boolean>; agree: Record<string, boolean>;
    flag_expected: boolean; flagged: boolean; all_agree: boolean }[]; check_agreement_pct: number; samples_fully_agreeing: number; total: number;
    key: { main_driver: string; second_factor: string }; cost_usd: number };
};

/** POST a question and read the Server-Sent Events stream until the reply arrives. */
export async function askStream(id: string, message: string, onEvent: (e: AgentEvent) => void, to?: Colleague): Promise<void> {
  const res = await fetch(`/api/game/${id}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, to: to && to !== "team" ? to : null }),
  });
  if (!res.ok || !res.body) throw new Error(`Ask failed (${res.status})`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const line = chunk.split("\n").find((l) => l.startsWith("data: "));
      if (line) onEvent(JSON.parse(line.slice(6)) as AgentEvent);
    }
  }
}
