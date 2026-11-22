// Prudential Financial-inspired palette: navy and white core, Prudential blue (#007AC1, Pantone 7461 C)
// as the accent, steel blue and gray as secondary colors. One place for every chart color.

export const NAVY = "#001F5B";
export const PRU_BLUE = "#007AC1";
export const LIGHT_BLUE = "#6CACE4";
export const STEEL = "#537D93";
export const GRAY = "#939598";
export const PALE = "#B9D9EB";
export const GOLD = "#E2A400";
export const EQUITY_COLOR = "#2E8540";

export const ASSET_COLORS: Record<string, string> = {
  govt: NAVY,
  ig_corp: PRU_BLUE,
  below_ig: LIGHT_BLUE,
  mortgage: STEEL,
  alts: GOLD,
  cash: PALE,
};

export const LIABILITY_COLORS: Record<string, string> = {
  annuities: PRU_BLUE,
  life: NAVY,
  prt: STEEL,
  other: GRAY,
  guarantee: "#C8102E",
};

export const ASSET_GROUPS = [
  { key: "bonds", label: "Bonds", color: "#0B3D7A", members: ["govt", "ig_corp", "below_ig"] },
  { key: "loans", label: "Mortgage loans", color: "#3E6577", members: ["mortgage"] },
  { key: "alts", label: "Alternatives (incl. stocks)", color: "#B88600", members: ["alts"] },
  { key: "cash", label: "Cash", color: "#8DBBD6", members: ["cash"] },
  { key: "other", label: "Other assets", color: "#7FA7C9", members: ["guarantee_asset", "mtm"] },
];

export const LIABILITY_GROUPS = [
  { key: "reserves", label: "Policy reserves", color: "#0B3D7A", members: ["annuities", "life", "prt"] },
  { key: "guarantees", label: "Market guarantees", color: "#9E0C24", members: ["guarantee"] },
  { key: "other", label: "Other", color: "#6E7072", members: ["other", "mtm"] },
];
