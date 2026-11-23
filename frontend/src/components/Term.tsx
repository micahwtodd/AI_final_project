import { createContext, useContext, type ReactNode } from "react";

export type Glossary = Record<string, { label: string; plain: string }>;
export const GlossaryContext = createContext<Glossary>({});

/** A term with its approved plain-English definition on hover or keyboard focus. */
export function Term(props: { k: string; children?: ReactNode; text?: ReactNode }) {
  // `text` replaces the glossary definition with box-specific help
  const g = useContext(GlossaryContext)[props.k];
  if (!g && !props.text) return <>{props.children}</>;
  return (
    <span className="term" tabIndex={0} aria-describedby={`def-${props.k}`}>
      {props.children ?? g?.label}
      <span className="term-pop" role="tooltip" id={`def-${props.k}`}>
        {!props.text && g && <b>{g.label}</b>}
        {props.text ?? g?.plain}
      </span>
    </span>
  );
}
