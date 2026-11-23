import { useEffect, useState } from "react";
import { api, type Company, type Debrief, type GameView, type Reveal, type Review, type Shock, type Usage } from "./api";
import { UsageMeter } from "./components/UsageMeter";
import { CompanySelect } from "./screens/CompanySelect";
import { Desk } from "./screens/Desk";
import { ShockScreen } from "./screens/ShockScreen";
import { RevealScreen } from "./screens/RevealScreen";
import { DebriefScreen } from "./screens/DebriefScreen";
import { SafetyLab } from "./screens/SafetyLab";
import { Experiments } from "./screens/Experiments";
import { QuizScreen } from "./screens/QuizScreen";
import { TraceScreen } from "./screens/TraceScreen";
import { UnderTheHood } from "./components/UnderTheHood";
import { GlossaryContext, type Glossary } from "./components/Term";
import { WelcomeScreen } from "./screens/WelcomeScreen";
import { SEASONS } from "./labels";
import { KnowledgeIntro } from "./screens/KnowledgeIntro";
import { CountUp } from "./components/Fx";
import { StreakChips } from "./components/Badges";
import { useSoundSwitch } from "./sound";

type Screen =
  | { name: "welcome" }
  | { name: "select" }
  | { name: "desk"; game: GameView }
  | { name: "shock"; game: GameView; shock: Shock; firstTry: { review: Review; question: string } | null }
  | { name: "reveal"; reveal: Reveal; shock: Shock }
  | { name: "debrief"; game: GameView; debrief: Debrief }
  | { name: "safety"; back: Screen }
  | { name: "trace"; game: GameView; back: Screen }
  | { name: "experiments"; back: Screen }
  | { name: "quiz"; game: GameView; when: "pre" | "post" }
  | { name: "knowledge"; game: GameView };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: "welcome" });
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [glossary, setGlossary] = useState<Glossary>({});
  const [lastPick, setLastPick] = useState<{ ticker: string; seed: number } | null>(null);  // so Back returns to the same company

  // The office outside changes with the quarter: spring, summer, fall, winter; shock screens are stormy.
  const sceneArt = (() => {
    if (screen.name === "desk") return `office_${SEASONS[Math.min(SEASONS.length - 1, screen.game.card?.quarter ?? screen.game.quarter)]}`;
    if (screen.name === "shock") return `office_${SEASONS[screen.shock.quarter]}_storm`;
    if (screen.name === "reveal") return `office_${SEASONS[screen.shock.quarter]}`;
    if (screen.name === "debrief" || (screen.name === "quiz" && screen.when === "post")) return "office_winter";
    return "office_day";
  })();
  useEffect(() => {  // preload every scene so a new quarter never flashes blank
    ["day", ...SEASONS.slice(1).flatMap((s) => [s, `${s}_storm`])].forEach((n) => { const i = new Image(); i.src = `/art/office_${n}.png`; });
  }, []);

  // Each new screen opens at the top, so the headline is the first thing the learner sees.
  useEffect(() => { window.scrollTo(0, 0); }, [screen.name]);

  useEffect(() => {
    api.companies().then(setCompanies).catch((e) => setError(String(e)));
    fetch("/api/glossary").then((r) => r.json()).then(setGlossary).catch(() => undefined);
  }, []);

  async function run<T>(fn: () => Promise<T>): Promise<T | undefined> {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      return undefined;
    } finally {
      setBusy(false);
    }
  }

  const liveGame = screen.name === "trace" ? null : "game" in screen ? screen.game : screen.name === "reveal" ? screen.reveal.view : null;
  const [lastGame, setLastGame] = useState<GameView | null>(null);
  useEffect(() => { if (liveGame) setLastGame(liveGame); }, [liveGame]);
  const game = liveGame ?? (screen.name === "select" || screen.name === "welcome" ? null : lastGame);

  async function switchMode(m: "solo" | "team") {
    if (!game) return;
    const r = await run(() => api.setMode(game.id, m));
    if (!r) return;
    const g2 = { ...game, agent_mode: r.agent_mode };
    setLastGame(g2);
    if (screen.name === "desk") setScreen({ name: "desk", game: g2 });
  }
  const [usage, setUsage] = useState<Usage | null>(null);
  const [sound, setSound] = useSoundSwitch();
  useEffect(() => {
    if (game?.usage) setUsage(game.usage);
  }, [game?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const mergeUsage = (u: Partial<Usage>) => setUsage((prev) => (prev ? { ...prev, ...u } : (u as Usage)));
  const quarterLabel =
    screen.name === "shock" || screen.name === "reveal"
      ? `Q${screen.shock.quarter} results`
      : screen.name === "debrief"
        ? "Game over"
        : `Quarter ${game ? Math.min(game.quarter, game.n_quarters) : 1} of ${game?.n_quarters ?? 5}`;
  const surplusShown =
    screen.name === "shock" ? screen.shock.surplus_after : game ? game.dashboard.surplus_usd_bn : 0;

  return (
    <GlossaryContext.Provider value={glossary}>
    <div className={`app scene-${screen.name}`} style={{ ["--scene" as string]: `url("/art/${sceneArt}.png")` }}>
      <header className="topbar">
        <div className="brand" onClick={() => setScreen({ name: "select" })} title="Back to company select">
          SURPLUS OR BUST
        </div>
        {game && (
          <div className="topbar-info">
            <span className="pill">{game.company}</span>
            <span className="pill">{quarterLabel}</span>
            <StreakChips a={game.achievements} />
            <span className="pill strong">Surplus <CountUp value={surplusShown} from={surplusShown} format={(v) => `$${v.toFixed(2)}bn`} /></span>
          </div>
        )}
        {game && usage && <UsageMeter gameId={game.id} usage={usage} onUsage={(u) => { setUsage(u); }} />}
        <button className={`pill sound-btn ${sound ? "on" : ""}`} onClick={() => setSound(!sound)}
          aria-pressed={sound} title={sound ? "Sound effects on (click to mute)" : "Sound effects off (click to turn on)"}>
          {sound ? "🔊 Sound on" : "🔇 Sound off"}
        </button>
        <UnderTheHood game={game} capUsd={usage?.budget_cap_usd ?? null} onMode={switchMode}
          onTrace={() => game && setScreen({ name: "trace", game, back: screen })}
          onSafety={() => setScreen({ name: "safety", back: screen })}
          onExperiments={() => setScreen({ name: "experiments", back: screen })} />
      </header>

      {error && (
        <div className="error" onClick={() => setError(null)}>
          {error} <span className="muted">(click to dismiss)</span>
        </div>
      )}

      <main key={screen.name} className="screen-in">
        {screen.name === "welcome" && <WelcomeScreen onDone={() => setScreen({ name: "select" })} />}
        {screen.name === "select" && (
          <CompanySelect
            companies={companies}
            busy={busy}
            initialPick={lastPick}
            onIntro={() => setScreen({ name: "welcome" })}
            onStart={async (ticker, seed, overrides) => {
              setLastPick({ ticker, seed });
              const g = await run(() => api.newGame(ticker, seed, false, overrides));
              if (g) setScreen({ name: "knowledge", game: g });
            }}
            onDemo={async () => {
              const g = await run(() => api.newGame("JXN", 409, true));
              if (g) setScreen({ name: "knowledge", game: g });
            }}
          />
        )}
        {screen.name === "knowledge" && (
          <KnowledgeIntro company={screen.game.company}
            onTake={() => setScreen({ name: "quiz", game: screen.game, when: "pre" })}
            onSkip={() => setScreen({ name: "desk", game: screen.game })}
            onBack={() => setScreen({ name: "select" })} />
        )}
        {screen.name === "desk" && (
          <Desk
            game={screen.game}
            busy={busy}
            run={run}
            onUpdate={(g) => setScreen({ name: "desk", game: g })}
            onShock={(shock) => setScreen({ name: "shock", game: screen.game, shock, firstTry: null })}
            usage={usage ?? screen.game.usage}
            onUsage={mergeUsage}
          />
        )}
        {screen.name === "shock" && (
          <ShockScreen
            key={`${screen.shock.quarter}-${screen.firstTry ? 2 : 1}`}
            shock={screen.shock}
            company={screen.game.company}
            gameId={screen.game.id}
            busy={busy}
            firstTry={screen.firstTry}
            onSubmit={async (text, notSure) => {
              const r = await run(() => api.explain(screen.game.id, text, notSure));
              api.usage(screen.game.id).then(setUsage).catch(() => undefined); // the examiner may have spent
              if (!r) return;
              if (r.final) setScreen({ name: "reveal", reveal: r, shock: screen.shock });
              else setScreen({ ...screen, firstTry: { review: r.review, question: r.question } });
            }}
          />
        )}
        {screen.name === "reveal" && (
          <RevealScreen
            reveal={screen.reveal}
            shock={screen.shock}
            onNext={async () => {
              const g = screen.reveal.view;
              if (screen.reveal.finished) {
                if (g.quiz_taken.includes("pre") && !g.quiz_taken.includes("post")) {
                  setScreen({ name: "quiz", game: g, when: "post" });
                  return;
                }
                const d = await run(() => api.debrief(g.id));
                if (d) setScreen({ name: "debrief", game: g, debrief: d });
              } else {
                setScreen({ name: "desk", game: g });
              }
            }}
          />
        )}
        {screen.name === "safety" && <SafetyLab onBack={() => setScreen(screen.back)} />}
        {screen.name === "trace" && <TraceScreen game={screen.game} onBack={() => setScreen(screen.back)} />}
        {screen.name === "experiments" && <Experiments onBack={() => setScreen(screen.back)} />}
        {screen.name === "quiz" && (
          <QuizScreen
            key={screen.when}
            gameId={screen.game.id}
            when={screen.when}
            company={screen.game.company}
            demo={screen.game.demo}
            onSkip={async () => {
              if (screen.when === "pre") { setScreen({ name: "desk", game: screen.game }); return; }
              const d = await run(() => api.debrief(screen.game.id));
              if (d) setScreen({ name: "debrief", game: screen.game, debrief: d });
            }}
            onBack={screen.when === "pre" ? () => setScreen({ name: "knowledge", game: screen.game }) : undefined}
            onDone={async () => {
              const g = screen.game;
              if (screen.when === "pre") {
                const fresh = await run(() => api.game(g.id));
                if (fresh) setScreen({ name: "desk", game: fresh });
              } else {
                const d = await run(() => api.debrief(g.id));
                if (d) setScreen({ name: "debrief", game: g, debrief: d });
              }
            }}
          />
        )}
        {screen.name === "debrief" && (
          <DebriefScreen debrief={screen.debrief} game={screen.game} onRestart={() => setScreen({ name: "select" })}
            onPlay={(ticker) => { setLastPick({ ticker, seed: screen.game.seed }); setScreen({ name: "select" }); }} />
        )}
      </main>

      <footer className="footer">Simplified training simulation. Not company policy or advice.</footer>
    </div>
    </GlossaryContext.Provider>
  );
}
