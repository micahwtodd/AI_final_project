import { PixelSprite } from "./PixelSprite";

export const GUIDE_STEPS = [
  { title: "Read the news wire", text: "Each quarter starts with a hint about what markets might do. It is a hint, not a forecast. Read it, then press Next." },
  { title: "Ask a colleague", text: "Click a sample question in the chat, or type your own. Vera sends it to the right specialist; you will see who did what and what it cost." },
  { title: "Sign a trade ticket", text: "Move a slider on the right (for example, cash on hand) and watch the dashboard update. Then press “Sign trade ticket”: nothing happens until you sign." },
  { title: "End the quarter", text: "Press “End quarter Q1”. The market moves, and Vera will ask you to explain what happened." },
];

export function GuideBar(props: { step: number; onNext: () => void; onHide: () => void }) {
  const s = GUIDE_STEPS[props.step];
  if (!s) return null;
  return (
    <div className="guide" role="status" aria-live="polite">
      <PixelSprite name="vera_pleased" size={44} className="guide-avatar" />
      <div className="guide-body">
        <div className="guide-step">Your first quarter · step {props.step + 1} of {GUIDE_STEPS.length}</div>
        <b>{s.title}</b>
        <div className="small">{s.text}</div>
      </div>
      <div className="guide-actions">
        {props.step < GUIDE_STEPS.length - 1 && <button className="chip" onClick={props.onNext}>Next</button>}
        <button className="link" onClick={props.onHide}>Hide guide</button>
      </div>
    </div>
  );
}
