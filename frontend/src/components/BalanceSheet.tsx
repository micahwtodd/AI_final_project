import type { Dashboard } from "../api";
import { ASSET_COLORS, ASSET_GROUPS, LIABILITY_COLORS, LIABILITY_GROUPS, EQUITY_COLOR } from "../theme";
import { ASSET_LABELS, LIABILITY_LABELS } from "../labels";

// ---------------------------------------------------------------- data

export type Segment = { key: string; label: string; value: number; color: string };

/** Both columns of the balance sheet, in $bn. They always total the same. */
export function balanceSheet(d: Dashboard): { assets: Segment[]; claims: Segment[]; total: number } {
  const assets: Segment[] = Object.entries(d.asset_values)
    .filter(([, v]) => v > 0.005)
    .map(([k, v]) => ({ key: k, label: ASSET_LABELS[k] ?? k, value: v, color: ASSET_COLORS[k] ?? "#999" }));
  const claims: Segment[] = Object.entries(d.liability_values)
    .filter(([k, v]) => v > 0.005 && !(k === "guarantee" && v <= 0))
    .map(([k, v]) => ({ key: k, label: LIABILITY_LABELS[k] ?? k, value: v, color: LIABILITY_COLORS[k] ?? "#999" }));
  // a negative guarantee value is a net asset (market risk benefit asset)
  const g = d.liability_values.guarantee ?? 0;
  if (g < -0.005) assets.push({ key: "guarantee_asset", label: "Guarantees (net asset)", value: -g, color: LIABILITY_COLORS.guarantee });
  const m = d.derivatives_mtm_usd_bn ?? 0;
  if (m > 0.005) assets.push({ key: "mtm", label: "Hedges owed by dealers", value: m, color: "#7FA7C9" });
  if (m < -0.005) claims.push({ key: "mtm", label: "Hedges owed to dealers", value: -m, color: "#7FA7C9" });
  claims.push({ key: "equity", label: "Equity (surplus)", value: Math.max(0, d.surplus_usd_bn), color: EQUITY_COLOR });
  const total = assets.reduce((s, x) => s + x.value, 0);
  return { assets, claims, total };
}

const fmt = (v: number) => (v >= 100 ? `$${v.toFixed(0)}bn` : `$${v.toFixed(1)}bn`);

// ---------------------------------------------------------------- stacked two-column bar

export function BalanceSheetBars(props: { dashboard: Dashboard; height?: number }) {
  const { assets, claims, total } = balanceSheet(props.dashboard);
  const H = props.height ?? 320;
  const colW = 96;
  const gap = 56;
  const top = 26;
  const W = colW * 2 + gap + 8;
  const scale = (H - top - 4) / Math.max(total, 1e-9);

  const column = (segs: Segment[], x: number, title: string) => {
    let y = top;
    return (
      <g>
        <text x={x + colW / 2} y={14} textAnchor="middle" className="bs-title">{title}</text>
        {segs.map((s) => {
          const h = s.value * scale;
          const rect = (
            <g key={s.key}>
              <rect x={x} y={y} width={colW} height={Math.max(h, 0.5)} fill={s.color} stroke="#fff" strokeWidth={1}>
                <title>{`${s.label}: $${s.value.toFixed(2)}bn (${((100 * s.value) / total).toFixed(1)}%)`}</title>
              </rect>
              {h >= 15 && (
                <text x={x + colW / 2} y={y + h / 2 + 4} textAnchor="middle" className="bs-seg-label"
                  fill={isLight(s.color) ? "#001F5B" : "#fff"}>{fmt(s.value)}</text>
              )}
            </g>
          );
          y += h;
          return rect;
        })}
      </g>
    );
  };

  return (
    <div className="bs-bars">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img"
        aria-label={`Balance sheet: assets $${total.toFixed(1)}bn; liabilities and equity $${total.toFixed(1)}bn`}>
        {column(assets, 4, "Assets")}
        {column(claims, 4 + colW + gap, "Liabilities + equity")}
      </svg>
      <div className="bs-total">Total ${total.toFixed(1)}bn</div>
    </div>
  );
}

function isLight(hex: string): boolean {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return 0.299 * r + 0.587 * g + 0.114 * b > 160;
}

// ---------------------------------------------------------------- concentric ring chart

function arc(cx: number, cy: number, r0: number, r1: number, a0: number, a1: number): string {
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const p = (r: number, a: number) => `${cx + r * Math.sin(a)} ${cy - r * Math.cos(a)}`;
  if (a1 - a0 >= 2 * Math.PI - 1e-6) a1 = a0 + 2 * Math.PI - 1e-4;
  return `M ${p(r1, a0)} A ${r1} ${r1} 0 ${large} 1 ${p(r1, a1)} L ${p(r0, a1)} A ${r0} ${r0} 0 ${large} 0 ${p(r0, a0)} Z`;
}

type Group = { key: string; label: string; color: string; members: string[] };

/** Inner ring: broad groups. Outer ring: each bucket. Legend with $ and %. */
export function RingChart(props: { title: string; segments: Segment[]; groups: Group[]; size?: number }) {
  const S = props.size ?? 220;
  const c = S / 2;
  const total = props.segments.reduce((s, x) => s + x.value, 0) || 1;
  const byKey = Object.fromEntries(props.segments.map((s) => [s.key, s]));
  const ordered = props.groups.flatMap((g) => g.members.filter((m) => byKey[m]).map((m) => byKey[m]));
  const leftovers = props.segments.filter((s) => !ordered.includes(s));
  const outer = [...ordered, ...leftovers];

  let a = 0;
  const outerArcs = outer.map((s) => {
    const a0 = a;
    a += (2 * Math.PI * s.value) / total;
    return { s, a0, a1: a };
  });
  a = 0;
  const innerArcs = props.groups
    .map((g) => ({ g, value: g.members.reduce((t, m) => t + (byKey[m]?.value ?? 0), 0) }))
    .filter((x) => x.value > 0)
    .map(({ g, value }) => {
      const a0 = a;
      a += (2 * Math.PI * value) / total;
      return { g, value, a0, a1: a };
    });

  return (
    <div className="ring">
      <h3>{props.title}</h3>
      <svg viewBox={`0 0 ${S} ${S}`} width={S} height={S} role="img" aria-label={props.title}>
        {innerArcs.map(({ g, value, a0, a1 }) => (
          <path key={g.key} d={arc(c, c, S * 0.2, S * 0.33, a0, a1)} fill={g.color} stroke="#fff" strokeWidth={1.5}>
            <title>{`${g.label}: $${value.toFixed(1)}bn (${((100 * value) / total).toFixed(1)}%)`}</title>
          </path>
        ))}
        {outerArcs.map(({ s, a0, a1 }) => (
          <path key={s.key} d={arc(c, c, S * 0.35, S * 0.49, a0, a1)} fill={s.color} stroke="#fff" strokeWidth={1.5}>
            <title>{`${s.label}: $${s.value.toFixed(1)}bn (${((100 * s.value) / total).toFixed(1)}%)`}</title>
          </path>
        ))}
        <text x={c} y={c - 2} textAnchor="middle" className="ring-total" style={{ fontSize: S * 0.075 }}>${total.toFixed(0)}bn</text>
        <text x={c} y={c + S * 0.065} textAnchor="middle" className="ring-sub" style={{ fontSize: S * 0.05 }}>total</text>
      </svg>
      <ul className="ring-legend">
        {innerArcs.map(({ g, value }) => (
          <li key={g.key} className="group">
            <span className="swatch" style={{ background: g.color }} />
            <b>{g.label}</b> <span className="muted">{fmt(value)} · {((100 * value) / total).toFixed(0)}%</span>
            {g.members.filter((m) => byKey[m]).length > 1 && <ul>
              {g.members.filter((m) => byKey[m]).map((m) => (
                <li key={m}>
                  <span className="swatch" style={{ background: byKey[m].color }} />
                  {byKey[m].label} <span className="muted">{fmt(byKey[m].value)} · {((100 * byKey[m].value) / total).toFixed(1)}%</span>
                </li>
              ))}
            </ul>}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- the three together

export function BalanceSheetPanel(props: { dashboard: Dashboard; compact?: boolean }) {
  const { assets, claims } = balanceSheet(props.dashboard);
  const liabOnly = claims.filter((c) => c.key !== "equity");
  const size = props.compact ? 180 : 220;
  return (
    <div className="bs-panel">
      <RingChart title="Asset breakdown" segments={assets} groups={ASSET_GROUPS} size={size} />
      <BalanceSheetBars dashboard={props.dashboard} height={props.compact ? 300 : 360} />
      <RingChart title="Liability breakdown" segments={liabOnly} groups={LIABILITY_GROUPS} size={size} />
    </div>
  );
}
