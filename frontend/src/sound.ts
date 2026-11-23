// Small synthesized sound effects (Web Audio, no files). Off by default; the top-bar switch turns them on.
import { useEffect, useState } from "react";

export type Sfx = "register" | "alarm" | "bell" | "badge" | "whoosh" | "click" | "boom" | "stamp";

const KEY = "riskdesk.sound";
let on = false;
try { on = localStorage.getItem(KEY) === "on"; } catch { /* storage may be blocked */ }
const listeners = new Set<(v: boolean) => void>();
let ctx: AudioContext | null = null;

export function soundOn() { return on; }
export function setSoundOn(v: boolean) {
  on = v;
  try { localStorage.setItem(KEY, v ? "on" : "off"); } catch { /* ignore */ }
  listeners.forEach((f) => f(v));
  if (v) play("click");
}
export function useSoundSwitch(): [boolean, (v: boolean) => void] {
  const [v, setV] = useState(on);
  useEffect(() => { listeners.add(setV); return () => { listeners.delete(setV); }; }, []);
  return [v, setSoundOn];
}

function audio(): AudioContext | null {
  try {
    ctx = ctx ?? new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
    if (ctx.state === "suspended") void ctx.resume();
    return ctx;
  } catch { return null; }
}

function tone(a: AudioContext, freq: number, start: number, dur: number, type: OscillatorType, vol: number, slideTo?: number) {
  const o = a.createOscillator();
  const g = a.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, a.currentTime + start);
  if (slideTo) o.frequency.exponentialRampToValueAtTime(slideTo, a.currentTime + start + dur);
  g.gain.setValueAtTime(0.0001, a.currentTime + start);
  g.gain.exponentialRampToValueAtTime(vol, a.currentTime + start + 0.01);
  g.gain.exponentialRampToValueAtTime(0.0001, a.currentTime + start + dur);
  o.connect(g).connect(a.destination);
  o.start(a.currentTime + start);
  o.stop(a.currentTime + start + dur + 0.05);
}

function noise(a: AudioContext, start: number, dur: number, vol: number) {
  const buf = a.createBuffer(1, Math.floor(a.sampleRate * dur), a.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length);
  const src = a.createBufferSource();
  const g = a.createGain();
  g.gain.value = vol;
  src.buffer = buf;
  src.connect(g).connect(a.destination);
  src.start(a.currentTime + start);
}

export function play(name: Sfx) {
  if (!on) return;
  const a = audio();
  if (!a) return;
  switch (name) {
    case "register": // drawer clunk, then the "ka-ching"
      noise(a, 0, 0.08, 0.25);
      tone(a, 2093, 0.08, 0.35, "triangle", 0.18);
      tone(a, 2637, 0.16, 0.5, "triangle", 0.16);
      break;
    case "alarm": // two-tone warning, three times
      for (let i = 0; i < 3; i++) {
        tone(a, 740, i * 0.32, 0.15, "square", 0.05);
        tone(a, 554, i * 0.32 + 0.16, 0.15, "square", 0.05);
      }
      break;
    case "bell": // a bright bell
      tone(a, 1318, 0, 1.2, "sine", 0.2);
      tone(a, 1976, 0, 0.9, "sine", 0.08);
      break;
    case "badge": // rising arpeggio
      [784, 988, 1175, 1568].forEach((f, i) => tone(a, f, i * 0.08, 0.3, "triangle", 0.12));
      break;
    case "whoosh":
      tone(a, 180, 0, 0.45, "sawtooth", 0.04, 900);
      break;
    case "click":
      tone(a, 880, 0, 0.06, "square", 0.04);
      break;
    case "boom": // a cartoon explosion: a falling whistle, then a long rumble
      tone(a, 1400, 0, 0.7, "sine", 0.06, 300);
      noise(a, 0.7, 1.8, 0.5);
      tone(a, 70, 0.7, 1.6, "sawtooth", 0.18, 30);
      break;
    case "stamp": // a rubber stamp thunk
      noise(a, 0, 0.06, 0.2);
      tone(a, 160, 0, 0.12, "square", 0.06, 90);
      break;
  }
}
