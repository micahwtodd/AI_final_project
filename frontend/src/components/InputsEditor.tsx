import type { GameInput } from "../api";

const toShown = (r: GameInput, v: number) => (r.unit === "pct" ? +(100 * v).toFixed(2) : +v.toFixed(r.unit === "x" ? 3 : 2));
const fromShown = (r: GameInput, v: number) => (r.unit === "pct" ? v / 100 : v);
const UNIT = { bn: "$bn", pct: "%", x: "×" } as const;

/** The figures the game runs on. Edit any of them to try your own assumptions; mixes are re-scaled to 100%. */
export function InputsEditor(props: {
  inputs: GameInput[];
  overrides: Record<string, number>;
  onChange: (o: Record<string, number>) => void;
  error: string | null;
}) {
  const groups = [...new Set(props.inputs.map((r) => r.group))];
  const edited = Object.keys(props.overrides).length;

  const set = (r: GameInput, raw: string) => {
    const n = Number(raw);
    const next = { ...props.overrides };
    if (raw.trim() === "" || Number.isNaN(n)) return;
    const v = fromShown(r, n);
    if (Math.abs(v - r.value) < 1e-9) delete next[r.key];
    else next[r.key] = v;
    props.onChange(next);
  };

  return (
    <div className="inputs-editor">
      <div className="inputs-head">
        <div>
          <b>Game inputs</b>
          <div className="small muted">What the game actually runs on. Change any figure to test your own view; the balance sheet above updates as you type.</div>
        </div>
        <button className="ghost" disabled={edited === 0} onClick={() => props.onChange({})}>Reset to Seamore's values{edited ? ` (${edited} edited)` : ""}</button>
      </div>
      {props.error && <div className="flag small">{props.error}</div>}
      <div className="inputs-groups">
        {groups.map((g) => (
          <table className="table inputs-table" key={g}>
            <thead><tr><th colSpan={2}>{g}{g.endsWith("mix") && <span className="muted small"> · re-scaled to 100%</span>}</th></tr></thead>
            <tbody>
              {props.inputs.filter((r) => r.group === g).map((r) => {
                const cur = props.overrides[r.key] ?? r.value;
                const isEdited = r.key in props.overrides;
                return (
                  <tr key={r.key} className={isEdited ? "edited" : ""}>
                    <td>{r.label}</td>
                    <td className="num">
                      <input type="number" step={r.unit === "pct" ? 0.1 : r.unit === "x" ? 0.05 : 0.1}
                        min={toShown(r, r.min)} max={toShown(r, r.max)}
                        value={toShown(r, cur)} aria-label={r.label}
                        onChange={(e) => set(r, e.target.value)} />
                      <span className="unit">{UNIT[r.unit]}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ))}
      </div>
    </div>
  );
}
