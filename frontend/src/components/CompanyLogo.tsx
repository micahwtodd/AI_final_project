import { useState } from "react";

// Logo files live in frontend/public/logos/{TICKER}.svg or .png. If none is present,
// a clean ticker badge is shown instead, so the page never shows a broken image.
const EXTS = ["svg", "png"];

export function CompanyLogo(props: { ticker: string; name: string }) {
  const [i, setI] = useState(0);
  if (i >= EXTS.length) {
    return (
      <div className="logo-badge" aria-label={`${props.name} logo placeholder`}>
        {props.ticker}
      </div>
    );
  }
  return (
    <img className="logo-img" src={`/logos/${props.ticker}.${EXTS[i]}`} alt={`${props.name} logo`}
      onError={() => setI((x) => x + 1)} />
  );
}
