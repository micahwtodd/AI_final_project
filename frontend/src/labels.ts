// Plain words first, the technical term second.

export const ASSET_LABELS: Record<string, string> = {
  govt: "Government bonds",
  ig_corp: "Investment-grade corporates",
  below_ig: "Junk bonds (below investment grade)",
  mortgage: "Mortgage loans",
  alts: "Alternatives (incl. stocks)",
  cash: "Cash",
};

export const LIABILITY_LABELS: Record<string, string> = {
  annuities: "Annuities (savings policies)",
  life: "Life insurance",
  prt: "Pensions taken over (pension risk transfer)",
  other: "Other",
  guarantee: "Stock-market guarantees (VA guarantees)",
};

export const SEASONS = ["", "spring", "summer", "fall", "winter", "crash"] as const;
export const SEASON_ICON: Record<string, string> = { spring: "🌸", summer: "☀️", fall: "🍂", winter: "❄️", crash: "💥" };
/** What each quarter is called on screen: the four seasons, then the boss round. */
export const SEASON_NAME: Record<string, string> = { spring: "spring", summer: "summer", fall: "fall", winter: "winter", crash: "the crash" };
/** The icon on each quarter's lesson card. */
export const LESSON_ICON: Record<number, string> = { 1: "📈", 2: "📉", 3: "🔻", 4: "💳", 5: "💥" };

export const LEVERS = {
  rate_hedge_pct: {
    term: "interest_rate_swap",
    label: "Rate protection (swaps)",
    help: "Closes this % of the rate mismatch between assets and liabilities. Costs a little each quarter.",
    tip: "Interest rate swaps that receive a fixed rate gain value when rates fall, so they close the rate mismatch between assets and liabilities: +100% closes all of it. Negative values pay fixed instead: they gain if rates rise but widen the mismatch. Costs a little each quarter.",
    min: -150, max: 150, step: 5, unit: "%",
  },
  credit_shift_pct: {
    term: "credit_spread",
    label: "Move risky bonds to government bonds",
    help: "Sells this % of junk and BBB bonds and buys government bonds. Safer, but earns less.",
    tip: "Sells this % of junk and BBB bonds and buys government bonds. Risky bonds pay extra yield (the credit spread): when spreads widen their prices fall, and a default is a permanent loss. Safer, but earns less. Negative values move back into riskier bonds.",
    min: -10, max: 50, step: 5, unit: "%",
  },
  equity_hedge_pct: {
    term: "put_option",
    label: "Stock-market insurance (puts)",
    help: "Protects this % of the guarantees you owe policyholders if markets fall. Costs a premium every quarter.",
    tip: "Put options pay out when stocks fall. They protect this % of the stock-market guarantees you owe policyholders, and cost a premium every quarter whether or not they pay.",
    min: 0, max: 100, step: 10, unit: "%",
  },
  cash_buffer_pct: {
    term: "forced_selling",
    label: "Cash on hand",
    help: "Cash as % of invested assets. Pays for surrenders and margin calls without selling bonds at a loss, but earns less.",
    tip: "Cash as % of invested assets. It pays surrenders and collateral calls without forced selling (selling bonds at a discount in a stressed market), but it earns less.",
    min: 1, max: 15, step: 1, unit: "%",
  },
} as const;

export type LeverKey = keyof typeof LEVERS;

/** When each lever unlocks (cash and puts are there from the start), and who introduces it. */
export const UNLOCK_Q: Record<string, number> = { rate_hedge_pct: 2, credit_shift_pct: 3, counterparty: 4 };
export const UNLOCK_INTRO: Record<string, { face: string; who: string; line: string }> = {
  rate_hedge_pct: { face: "swap_pleased", who: "Swap Dogg", line: "New toy, man: interest rate swaps. Slide right to receive fixed (gains if rates fall); slide left to pay fixed, which is a bet that rates rise, not protection." },
  credit_shift_pct: { face: "bonnie_pleased", who: "Bonnie", line: "You can now move risky bonds into government bonds. Safer when defaults come, but we give up yield." },
  counterparty: { face: "swap_neutral", who: "Swap Dogg", line: "Counterparty terms are yours now: daily collateral and more dealers cut what a dealer failure can cost us." },
};

export const COUNTERPARTY_TIP = "With daily collateral, dealers post cash as your hedges gain, so a dealer failure costs little; it can also demand cash from you when hedges lose. Spreading hedges across 3 dealers limits what any one failure can cost.";
export const TICKET_TIP = "Each slider starts at zero every quarter: it is a new trade added on top of what you already hold. Your positions carry over from quarter to quarter.";

export const fmtBn = (x: number, digits = 2) => `${x < 0 ? "−" : ""}$${Math.abs(x).toFixed(digits)}bn`;
export const fmtSigned = (x: number, digits = 2) => `${x >= 0 ? "+" : "−"}$${Math.abs(x).toFixed(digits)}bn`;

export function fmtMove(value: number | null, unit: string): string {
  if (value === null) return unit;
  if (unit === "x") return `${value.toFixed(2)}×`;
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(unit === "bp" ? 0 : 1)}${unit === "bp" ? " bp" : "%"}`;
}
