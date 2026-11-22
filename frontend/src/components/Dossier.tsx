import { Fragment, useState } from "react";
import type { Company } from "../api";
import { PixelSprite } from "./PixelSprite";

const BADGE: Record<string, { label: string; cls: string; tip: string }> = {
  tagged: { label: "Tagged", cls: "b-tagged", tip: "Read by code from the 10-K's tagged XBRL financial data" },
  filing_text: { label: "Filing text", cls: "b-text", tip: "Read by Seamore from the 10-K text; the quote was checked word-for-word by code" },
  derived: { label: "Derived", cls: "b-derived", tip: "Computed by code from tagged or text figures" },
  assumption: { label: "Assumption", cls: "b-assume", tip: "Labelled default: not disclosed consistently, editable in data/assumptions.json" },
};

function fmt(v: number, unit: string) {
  return unit === "pct" ? `${(100 * v).toFixed(1)}%` : `${v < 0 ? "−" : ""}$${Math.abs(v).toFixed(1)}bn`;
}

export function Dossier(props: { company: Company }) {
  const c = props.company;
  const [open, setOpen] = useState<string | null>(null);
  const counts = c.dossier.reduce<Record<string, number>>((m, r) => ({ ...m, [r.source]: (m[r.source] ?? 0) + 1 }), {});

  return (
    <div className="dossier-box">
      <div className="dossier-intro">
        <PixelSprite name="seamore_neutral" size={56} className="sam-face" title="Seamore Tenkays" />
        <div>
          <div className="cro-name">Seamore Tenkays · Calibration Analyst</div>
          <div className="small">“It's in the notes.” Here is how I built this balance sheet from {c.name}'s FY{c.fiscal_year} 10-K
            (accession {c.accession}). Every figure shows where it came from; click a row for the citation. To change what the game uses, edit the inputs above.</div>
          <div className="badge-row">
            {Object.entries(BADGE).map(([k, b]) => (
              <span key={k} className={`badge ${b.cls}`} title={b.tip}>{b.label} {counts[k] ?? 0}</span>
            ))}
          </div>
        </div>
      </div>
      <table className="table dossier-table">
        <thead><tr><th>Figure</th><th className="num">Value</th><th>Source</th></tr></thead>
        <tbody>
          {c.dossier.map((r) => (
            <Fragment key={r.key}>
              <tr className="clickable" onClick={() => setOpen(open === r.key ? null : r.key)}>
                <td>{r.label}</td>
                <td className="num">{fmt(r.value, r.unit)}</td>
                <td><span className={`badge ${BADGE[r.source].cls}`} title={BADGE[r.source].tip}>{BADGE[r.source].label}</span></td>
              </tr>
              {open === r.key && (
                <tr className="cite-row"><td colSpan={3}>
                  {r.citation && <div className="small"><b>Citation:</b> {r.citation}</div>}
                  {r.note && <div className="small muted">{r.note}</div>}
                </td></tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
      {Object.keys(c.reference).length > 0 && (
        <div className="small reference">
          <b>Also disclosed (for reference, not used by the engine):</b>
          <ul>
            {Object.entries(c.reference).map(([k, r]) => (
              <li key={k}>{r.note.split(".")[0]}: <b>${r.value.toFixed(2)}bn</b> <span className="muted">· {r.citation}</span></li>
            ))}
          </ul>
        </div>
      )}
      {c.rejections.length > 0 && (
        <div className="small muted">
          Readings I rejected after checking them: {c.rejections.map((r) => `${r.field} (${r.reason})`).join("; ")}.
        </div>
      )}
    </div>
  );
}
