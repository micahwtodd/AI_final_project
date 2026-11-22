const COLORS = ["#4f8cff", "#36c5a0", "#f2b134", "#e86f5c", "#a77bf3", "#5ed0e6", "#9aa5b8"];

export function MixBar(props: { mix: Record<string, number>; labels: Record<string, string>; values?: boolean }) {
  const entries = Object.entries(props.mix).filter(([, v]) => v > 0.0005);
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1;
  return (
    <div className="mixbar">
      <div className="mixbar-track">
        {entries.map(([k, v], i) => (
          <div
            key={k}
            className="mixbar-seg"
            style={{ width: `${(100 * v) / total}%`, background: COLORS[i % COLORS.length] }}
            title={`${props.labels[k] ?? k}: ${props.values ? `$${v.toFixed(1)}bn` : `${((100 * v) / total).toFixed(1)}%`}`}
          />
        ))}
      </div>
      <ul className="mixbar-legend">
        {entries.map(([k, v], i) => (
          <li key={k}>
            <span className="swatch" style={{ background: COLORS[i % COLORS.length] }} />
            {props.labels[k] ?? k}
            <span className="muted">
              {props.values ? ` $${v.toFixed(1)}bn` : ` ${((100 * v) / total).toFixed(1)}%`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
