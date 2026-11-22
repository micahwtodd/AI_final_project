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

export const LEVERS = {
  rate_hedge_pct: {
    term: "interest_rate_swap",
    label: "Rate protection (swaps)",
    help: "Closes this % of the rate mismatch between assets and liabilities. Costs a little each quarter.",
    min: 0, max: 120, step: 5, unit: "%",
  },
  credit_shift_pct: {
    term: "credit_spread",
    label: "Move risky bonds to government bonds",
    help: "Sells this % of junk and BBB bonds and buys government bonds. Safer, but earns less.",
    min: -10, max: 30, step: 5, unit: "%",
  },
  equity_hedge_pct: {
    term: "put_option",
    label: "Stock-market insurance (puts)",
    help: "Protects this % of the guarantees you owe policyholders if markets fall. Costs a premium every quarter.",
    min: 0, max: 100, step: 10, unit: "%",
  },
  cash_buffer_pct: {
    term: "forced_selling",
    label: "Cash on hand",
    help: "Cash as % of invested assets. Pays for surrenders and margin calls without selling bonds at a loss, but earns less.",
    min: 1, max: 15, step: 1, unit: "%",
  },
} as const;

export type LeverKey = keyof typeof LEVERS;

export const fmtBn = (x: number, digits = 2) => `${x < 0 ? "−" : ""}$${Math.abs(x).toFixed(digits)}bn`;
export const fmtSigned = (x: number, digits = 2) => `${x >= 0 ? "+" : "−"}$${Math.abs(x).toFixed(digits)}bn`;

export function fmtMove(value: number | null, unit: string): string {
  if (value === null) return unit;
  if (unit === "x") return `${value.toFixed(2)}×`;
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(unit === "bp" ? 0 : 1)}${unit === "bp" ? " bp" : "%"}`;
}
