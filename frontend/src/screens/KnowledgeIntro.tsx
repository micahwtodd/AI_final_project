import { PixelSprite } from "../components/PixelSprite";

/** The page between picking a company and the quiz: what the Knowledge Check is for, with a skip. */
export function KnowledgeIntro(props: { company: string; onTake: () => void; onSkip: () => void; onBack: () => void }) {
  return (
    <section className="welcome">
      <div className="intro-card knowledge-card">
        <div className="intro-top">
          <span className="intro-kicker">Knowledge Check</span>
          <button className="link" onClick={props.onBack}>← Back to companies</button>
        </div>
        <div className="intro-main">
          <div className="intro-art"><PixelSprite name="vera_neutral" size={130} title="Vera Atrisk" /></div>
          <div className="intro-text">
            <h2>Before you start, want to test your understanding of fundamental risk management principles?</h2>
            <div className="intro-body">
              <p>Five quick questions, then five quick confidence ratings. It takes about three minutes and does not count
                toward your score. Check each answer as you go to see the explanation.</p>
              <p className="intro-note">At the end of the year you can take a second set on the same ideas and see how far
                you came running {props.company}.</p>
            </div>
          </div>
        </div>
        <div className="intro-nav">
          <button className="ghost" onClick={props.onBack}>← Back</button>
          <div className="knowledge-actions">
            <button className="ghost" onClick={props.onSkip}>Skip for now</button>
            <button className="gold-btn" onClick={props.onTake}>Take the Knowledge Check →</button>
          </div>
        </div>
      </div>
    </section>
  );
}
