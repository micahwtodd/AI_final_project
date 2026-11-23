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
    body: <>Welcome aboard! You're the new junior risk analyst at a real US life insurer. You have <b>four quarters</b> to
      keep the company standing… but the markets will not be kind.</>,
    art: <PixelSprite name="cat_alert" size={150} title="Convexity the office cat, on alert" />,
  },
  {
    kicker: "How this works", title: "Assets − liabilities = equity.",
    body: <>
      <p>Your company has <b>assets</b> (money you have or are owed), and <b>liabilities</b> (money you owe to others).
        <b> Equity</b> is what is left over. Each component has different sensitivities to financial market risks.</p>
      <p>You must navigate the company through tumultuous markets: success is measured by <b>how much equity you preserve
        and grow</b>. You must rely on your elite team of experts for guidance, evaluate their feedback, recommend
        protective trades, and explain your decisions to the CRO.</p>
      <p className="intro-note">The underlying data is based on real financials. These simulations will teach you how
        different companies have different exposures.</p>
    </>,
    art: <PixelSprite name="cat_nap" size={150} title="Convexity the office cat, napping" />,
  },
  {
    kicker: "Your boss", title: "Vera Atrisk, Chief Risk Officer",
    body: <>Vera runs the organization, sends your questions to the right expert, and will ask you to explain your
      decisions after every market shock.</>,
    art: <PixelSprite name="vera_neutral" size={150} title="Vera Atrisk" />,
  },
  {
    kicker: "Your team", title: "Three specialists. Three opinions.",
    body: <div className="intro-team">
      <Face name="morty_neutral" who="Morty Tables" role="Actuary"
        line="An expert in policyholder liabilities: what you owe, when policyholders cash out, and the guarantees you've promised." />
      <Face name="bonnie_neutral" who="Bonnie Yields" role="Portfolio Manager"
        line="Understands fixed-income assets: bonds, credit quality, and where the yield comes from." />
      <Face name="swap_neutral" who="Swap Dogg" role="Trader"
        line="Understands derivatives: interest rate swaps, stock-market options, and the dealers on the other side." />
    </div>,
    art: null,
  },
  {
    kicker: "Behind the scenes", title: "Seamore reads the 10-Ks with the company cat, Convexity.",
    body: <div className="intro-team">
      <Face name="seamore_neutral" who="Seamore Tenkays" role="Calibration Analyst"
        line="Read the company's latest 10-K annual report and cited every number. These are real financial metrics!" />
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
    kicker: "How to play", title: "Read. Ask. Trade. Survive. Explain.",
    body: <ol className="intro-steps">
      <li><b>Read the wire</b> for a hint of what's coming.</li>
      <li><b>Ask your team</b> anything.</li>
      <li><b>Sign a trade ticket:</b> hedge, de-risk or hold cash.</li>
      <li><b>The market hits.</b></li>
      <li><b>Explain it to Vera</b> to score points.</li>
    </ol>,
    art: null,
  },
  {
    kicker: "How to win", title: "Scoring has two categories.",
    body: <div className="score-cats">
      <div className="score-cat"><span className="score-n">1</span>
        <div><b>Results</b><div>Beat doing nothing and get close to what a pro would do.</div></div></div>
      <div className="score-cat"><span className="score-n">2</span>
        <div><b>The Executive Summary</b><div>Explain what really happened in your own words, and Vera will critique you.</div></div></div>
      <p className="intro-warn">Every hedge costs money, so be thoughtful.</p>
    </div>,
    art: <PixelSprite name="vera_pleased" size={150} title="Vera Atrisk" />,
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
            {["morty", "bonnie", "vera", "swap", "seamore"].map((w, k) => (
              <span key={w} className="bob" style={{ animationDelay: `${k * 0.15}s` }}>
                <PixelSprite name={`${w}_${stage === "too-bad" ? "concerned" : "pleased"}`} size={w === "vera" ? 128 : 96} />
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
