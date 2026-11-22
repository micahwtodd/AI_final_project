import { useEffect, useState } from "react";
import { api, type Company, type Debrief, type GameView, type Health, type Reveal, type Review, type Shock, type Usage } from "./api";
import { UsageMeter } from "./components/UsageMeter";
import { CompanySelect } from "./screens/CompanySelect";
import { Desk } from "./screens/Desk";
import { ShockScreen } from "./screens/ShockScreen";
import { RevealScreen } from "./screens/RevealScreen";
import { DebriefScreen } from "./screens/DebriefScreen";

type Screen =
  | { name: "select" }
  | { name: "desk"; game: GameView }
  | { name: "shock"; game: GameView; shock: Shock; firstTry: { review: Review; question: string } | null }
  | { name: "reveal"; reveal: Reveal; shock: Shock }
  | { name: "debrief"; game: GameView; debrief: Debrief };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: "select" });
  const [companies, setCompanies] = useState<Company[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.companies().then(setCompanies).catch((e) => setError(String(e)));
    api.health().then(setHealth).catch(() => setHealth(null));
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

  const game = "game" in screen ? screen.game : screen.name === "reveal" ? screen.reveal.view : null;
  const [usage, setUsage] = useState<Usage | null>(null);
  useEffect(() => {
    if (game?.usage) setUsage(game.usage);
  }, [game?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const mergeUsage = (u: Partial<Usage>) => setUsage((prev) => (prev ? { ...prev, ...u } : (u as Usage)));
  const quarterLabel =
    screen.name === "shock" || screen.name === "reveal"
      ? `Q${screen.shock.quarter} results`
      : screen.name === "debrief"
        ? "Year end"
        : `Quarter ${game ? Math.min(game.quarter, 4) : 1} of 4`;
  const surplusShown =
    screen.name === "shock" ? screen.shock.surplus_after : game ? game.dashboard.surplus_usd_bn : 0;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand" onClick={() => setScreen({ name: "select" })} title="Back to company select">
          RISK DESK
        </div>
        {game && (
          <div className="topbar-info">
            <span className="pill">{game.company}</span>
            <span className="pill">{quarterLabel}</span>
            <span className="pill">Seed {game.seed}</span>
            <span className="pill strong">Surplus ${surplusShown.toFixed(2)}bn</span>
          </div>
        )}
        {game && usage && <UsageMeter gameId={game.id} usage={usage} onUsage={(u) => { setUsage(u); }} />}
        <div className={`pill status ${health?.key_found ? "ok" : "off"}`}>
          {health?.key_found ? `AI colleagues: ${health.model} ready` : "AI colleagues offline"}
        </div>
      </header>

      {error && (
        <div className="error" onClick={() => setError(null)}>
          {error} <span className="muted">(click to dismiss)</span>
        </div>
      )}

      <main>
        {screen.name === "select" && (
          <CompanySelect
            companies={companies}
            busy={busy}
            onStart={async (ticker, seed) => {
              const g = await run(() => api.newGame(ticker, seed));
              if (g) setScreen({ name: "desk", game: g });
            }}
          />
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
                const d = await run(() => api.debrief(g.id));
                if (d) setScreen({ name: "debrief", game: g, debrief: d });
              } else {
                setScreen({ name: "desk", game: g });
              }
            }}
          />
        )}
        {screen.name === "debrief" && (
          <DebriefScreen debrief={screen.debrief} game={screen.game} onRestart={() => setScreen({ name: "select" })} />
        )}
      </main>

      <footer className="footer">Simplified training simulation. Not company policy or advice.</footer>
    </div>
  );
}
