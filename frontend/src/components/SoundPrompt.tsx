import { useState } from "react";
import { setSoundOn, soundOn } from "../sound";

const KEY = "riskdesk.soundAsked";

/** Asks once whether to play with sound (off by default, for classrooms and offices). */
export function SoundPrompt() {
  const [show, setShow] = useState(() => {
    try { return !soundOn() && !localStorage.getItem(KEY); } catch { return false; }
  });
  if (!show) return null;
  const answer = (on: boolean) => {
    try { localStorage.setItem(KEY, "1"); } catch { /* private mode */ }
    if (on) setSoundOn(true);
    setShow(false);
  };
  return (
    <div className="sound-prompt" role="dialog" aria-label="Sound effects">
      <span>🔊 Play with sound effects? Stamps, clicks, the market bell.</span>
      <button className="gold-btn" onClick={() => answer(true)}>Sound on</button>
      <button className="link" onClick={() => answer(false)}>No thanks</button>
    </div>
  );
}
