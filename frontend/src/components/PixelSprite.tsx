import { useEffect, useRef } from "react";
import data from "../sprites/sprites.json";

type SpriteData = { palette: string[]; sprites: Record<string, string[]> };
const SPRITES = data as SpriteData;

export type Mood = "neutral" | "pleased" | "concerned";

// Which portrait each agent uses.
const FACE: Record<string, string> = {
  solo: "amara", cro: "amara", examiner: "amara",
  actuary: "walt", portfolio_manager: "priya", trader: "teo", calibration: "sam", sam: "sam",
};

export function spriteFor(agent: string | undefined, mood: Mood = "neutral"): string | null {
  const who = agent ? FACE[agent] : undefined;
  return who ? `${who}_${mood}` : null;
}

/** Draws one sprite from sprites.json on a canvas, scaled with crisp pixels. */
export function PixelSprite(props: { name: string; size: number; title?: string; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const rows = SPRITES.sprites[props.name];

  useEffect(() => {
    const cv = ref.current;
    if (!cv || !rows) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, cv.width, cv.height);
    rows.forEach((row, y) => {
      for (let x = 0; x < row.length; x++) {
        const i = parseInt(row[x], 16);
        if (i === 0) continue;
        ctx.fillStyle = SPRITES.palette[i];
        ctx.fillRect(x, y, 1, 1);
      }
    });
  }, [rows]);

  if (!rows) return null;
  return (
    <canvas ref={ref} width={rows[0].length} height={rows.length} className={`pixel ${props.className ?? ""}`}
      style={{ width: props.size, height: props.size * rows.length / rows[0].length }}
      role={props.title ? "img" : undefined} aria-label={props.title} aria-hidden={props.title ? undefined : true} />
  );
}

/** The Convexity cat reacts to the capital ratio: naps when healthy, sits up on a warning, hides under the desk on a breach. */
export function DeskCat(props: { status: "green" | "amber" | "red" | undefined; size?: number }) {
  const state = props.status === "red" ? "hide" : props.status === "amber" ? "alert" : "nap";
  const label = { nap: "Convexity the cat is napping: capital is healthy",
    alert: "Convexity the cat is on alert: capital is near the floor",
    hide: "Convexity the cat is hiding: capital is below the floor" }[state];
  return <span className="desk-cat" title={label}><PixelSprite name={`cat_${state}`} size={props.size ?? 48} title={label} /></span>;
}
