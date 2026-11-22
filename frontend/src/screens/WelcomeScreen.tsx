import { useEffect, useState, type ReactNode } from "react";
import { PixelSprite } from "../components/PixelSprite";

type Slide = { kicker: string; title: string; body: ReactNode; art: ReactNode };

const Face = (p: { name: string; who: string; role: string; line: string }) => (
  <div className="intro-person">
    <PixelSprite name={p.name} size={84} title={p.who} />
    <div>
      <b>{p.who}</b> <span className="intro-role">{p.role}</span>
      <div className="small">{p.line}</div>
    </div>
  </div>
);

const SLIDES: Slide[] = [
  {
    kicker: "The job", title: "You just got hired.",
    body: <>You're the new junior risk analyst at a real US life insurer. You have <b>four quarters</b>. The markets
      will not be kind. Keep the company standing.</>,
    art: <PixelSprite name="cat_alert" size={150} title="Convexity the office cat, on alert" />,
  },
  {
    kicker: "Your boss", title: "Dr. Amara Okafor, Chief Risk Officer",
    body: <>She runs the desk, sends your questions to the right expert, and after every market shock she asks
      you one thing: <b>“Walk me through why.”</b></>,
    art: <div className="intro-moods">
      <PixelSprite name="amara_pleased" size={96} title="Amara, pleased" />
      <PixelSprite name="amara_concerned" size={96} title="Amara, concerned" />
    </div>,
  },
  {
    kicker: "Your team", title: "Three specialists. Three opinions.",
    body: <div className="intro-team">
      <Face name="walt_neutral" who="Walt" role="Actuary" line="Policyholders, surrenders and guarantees." />
      <Face name="priya_neutral" who="Priya" role="Portfolio Manager" line="Bonds, credit and where the yield comes from." />
      <Face name="teo_neutral" who="Teo" role="Trader" line="Swaps, puts, forwards, and the dealers behind them." />
    </div>,
    art: null,
  },
  {
    kicker: "Behind the scenes", title: "Sam built your balance sheet. The cat watches it.",
    body: <div className="intro-team">
      <Face name="sam_neutral" who="Sam" role="Calibration Analyst" line="Read the company's annual report and cited every number." />
      <div className="intro-person">
        <div className="intro-cats">
          <PixelSprite name="cat_nap" size={56} title="napping" />
          <PixelSprite name="cat_alert" size={56} title="alert" />
          <PixelSprite name="cat_hide" size={56} title="hiding" />
        </div>
        <div><b>Convexity</b> <span className="intro-role">Office cat</span>
          <div className="small">Naps when capital is fine. Hides under the desk when it isn't.</div></div>
      </div>
    </div>,
    art: null,
  },
  {
    kicker: "Each quarter", title: "Read. Ask. Trade. Survive. Explain.",
    body: <ol className="intro-steps">
      <li><b>Read the wire</b> for a hint of what's coming.</li>
      <li><b>Ask your team</b> anything.</li>
      <li><b>Sign a trade ticket:</b> hedge, de-risk or hold cash.</li>
      <li><b>The market hits.</b></li>
      <li><b>Explain it to Amara</b> to score points.</li>
    </ol>,
    art: null,
  },
  {
    kicker: "How to win", title: "Two scores. No free lunch.",
    body: <>
      <p><b>Results:</b> beat doing nothing and get close to the expert benchmark.</p>
      <p><b>Understanding:</b> explain what really happened, in your own words.</p>
      <p className="intro-warn">Every hedge costs money. Hedge everything and you lose anyway.</p>
    </>,
    art: <PixelSprite name="amara_pleased" size={150} title="Dr. Amara Okafor" />,
  },
];

export function WelcomeScreen(props: { onDone: () => void }) {
  const [stage, setStage] = useState<"ask" | "too-bad" | "intro">("ask");
  const [i, setI] = useState(0);

  useEffect(() => {
    if (stage !== "too-bad") return;
    const t = setTimeout(() => setStage("intro"), 1900);
    return () => clearTimeout(t);
  }, [stage]);

  useEffect(() => {
    if (stage !== "intro") return;
    const key = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setI((x) => Math.min(SLIDES.length - 1, x + 1));
      if (e.key === "ArrowLeft") setI((x) => Math.max(0, x - 1));
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [stage]);

  if (stage !== "intro") {
    return (
      <section className="welcome">
        <div className="welcome-card">
          <div className="welcome-cast">
            {["walt", "priya", "amara", "teo", "sam"].map((w, k) => (
              <span key={w} className="bob" style={{ animationDelay: `${k * 0.15}s` }}>
                <PixelSprite name={`${w}_${stage === "too-bad" ? "concerned" : "pleased"}`} size={w === "amara" ? 96 : 72} />
              </span>
            ))}
          </div>
          <h1 className="welcome-title">Welcome, Junior Risk Analyst!</h1>
          <p className="welcome-sub">Are you ready to run a life insurance company?</p>
          {stage === "ask" ? (
            <div className="welcome-buttons">
              <button className="go-btn" onClick={() => setStage("intro")}>What are we waiting for?! Let's GOOOOOO 🚀</button>
              <button className="nope-btn" onClick={() => setStage("too-bad")}>No, this sounds incredibly boring.</button>
            </div>
          ) : (
            <div className="too-bad" role="status">Too bad! It's your job.</div>
          )}
        </div>
      </section>
    );
  }

  const s = SLIDES[i];
  const last = i === SLIDES.length - 1;
  return (
    <section className="welcome">
      <div className="intro-card" key={i}>
        <div className="intro-top">
          <span className="intro-kicker">{s.kicker}</span>
          <button className="link" onClick={props.onDone}>Skip intro</button>
        </div>
        <div className={`intro-main ${s.art ? "" : "no-art"}`}>
          {s.art && <div className="intro-art">{s.art}</div>}
          <div className="intro-text">
            <h2>{s.title}</h2>
            <div className="intro-body">{s.body}</div>
          </div>
        </div>
        <div className="intro-nav">
          <button className="ghost" disabled={i === 0} onClick={() => setI(i - 1)}>← Back</button>
          <div className="dots" aria-label={`Slide ${i + 1} of ${SLIDES.length}`}>
            {SLIDES.map((_, k) => <button key={k} className={`dot ${k === i ? "on" : ""}`} onClick={() => setI(k)} aria-label={`Slide ${k + 1}`} />)}
          </div>
          <button className="primary" onClick={() => (last ? props.onDone() : setI(i + 1))}>
            {last ? "Pick your company →" : "Next →"}
          </button>
        </div>
      </div>
    </section>
  );
}
