export type Mood = "neutral" | "pleased" | "concerned";

// Which portrait each agent uses.
const FACE: Record<string, string> = {
  solo: "vera", cro: "vera", examiner: "vera",
  actuary: "morty", portfolio_manager: "bonnie", trader: "swap", calibration: "seamore", sam: "seamore",
};

export function spriteFor(agent: string | undefined, mood: Mood = "neutral"): string | null {
  const who = agent ? FACE[agent] : undefined;
  return who ? `${who}_${mood}` : null;
}

/** One sprite from public/art (drawn by scripts/render_sprites.py), scaled with crisp pixels.
 *  Portraits are round badges; the cat has a transparent background. */
export function PixelSprite(props: { name: string; size: number; title?: string; className?: string }) {
  const portrait = !props.name.startsWith("cat_");
  return (
    <img src={`/art/${props.name}.png`} width={props.size} height={props.size} draggable={false}
      className={`pixel ${portrait ? "portrait" : ""} ${props.className ?? ""}`}
      alt={props.title ?? ""} aria-hidden={props.title ? undefined : true} />
  );
}

/** The Convexity cat reacts to the capital ratio: naps when healthy, sits up on a warning, hides under the desk on a breach. */
export function DeskCat(props: { status: "green" | "amber" | "red" | undefined; size?: number }) {
  const state = props.status === "red" ? "hide" : props.status === "amber" ? "alert" : "nap";
  const label = { nap: "Convexity the cat is napping: capital is healthy",
    alert: "Convexity the cat is on alert: capital is near the floor",
    hide: "Convexity the cat is hiding: capital is below the floor" }[state];
  return <span className={`desk-cat cat-${state}`} key={state} title={label}><PixelSprite name={`cat_${state}`} size={props.size ?? 48} title={label} /></span>;
}
