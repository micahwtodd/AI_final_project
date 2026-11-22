"""Safety layer (code). Project 6 uses the filing sanitizer; Project 7 adds the chat guards.

Filing sanitizer: what the program does to a document before any model sees it.
- drops HTML comments, <script>/<style>, and hidden elements (display:none, visibility:hidden,
  zero font size, zero opacity, off-screen positioning, white-on-white text, the hidden iXBRL header)
- removes zero-width and other invisible characters
- quarantines text that looks like instructions to an AI, so it never reaches a prompt
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

ZERO_WIDTH = re.compile("[​‌‍‎‏⁠⁡⁢⁣⁤﻿­]")

HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(?:\.0+)?(?:px|pt|em|rem|%)?\s*(?:;|$)"
    r"|opacity\s*:\s*0(?:\.0+)?\s*(?:;|$)|(?:left|top|text-indent)\s*:\s*-\d{4,}"
    r"|color\s*:\s*(?:#fff(?:fff)?|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))\b",
    re.I,
)

INSTRUCTION_LIKE = [
    r"\bignore (all |any |the |previous |prior |above )*(instructions|rules|prompts?)\b",
    r"\b(you are|you're) (now )?(an? |the )?(ai|assistant|language model|calibration analyst|model)\b",
    r"\b(as an ai|system prompt|developer message|new instructions)\b",
    r"\boverride (your|the|all|any|previous|prior) (instructions|rules|safety|guidelines|prompt)\b",
    r"\b(report|set|use|state|record) (the )?(value|figure|number|share|ratio) (as|to|of) \d",
    r"\bdo not (tell|reveal|mention)\b",
    r"\b(assistant|ai|model)s?\s*[:,-]\s*(please )?(set|report|ignore|say|output)\b",
]

BLOCK_TAGS = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "section", "ul", "ol"}
CELL_TAGS = {"td", "th"}
SKIP_TAGS = {"script", "style", "head", "title", "ix:header"}
VOID_TAGS = {"br", "img", "hr", "meta", "link", "input"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[tuple[str, bool]] = []  # (tag, hidden)
        self.dropped_hidden = 0
        self.dropped_comments = 0

    def _hidden(self) -> bool:
        return any(h for _, h in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        hidden = tag in SKIP_TAGS or "hidden" in a or bool(HIDDEN_STYLE.search(a.get("style") or ""))
        if hidden and not self._hidden():
            self.dropped_hidden += 1
        if tag not in VOID_TAGS:
            self.stack.append((tag, hidden))
        if not self._hidden():
            if tag in BLOCK_TAGS:
                self.out.append("\n")
            elif tag in CELL_TAGS:
                self.out.append(" | ")

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if not self._hidden() and tag in BLOCK_TAGS:
            self.out.append("\n")

    def handle_data(self, data):
        if not self._hidden():
            self.out.append(data)

    def handle_comment(self, data):
        self.dropped_comments += 1  # comments are never kept


def html_to_text(html: str) -> tuple[str, dict]:
    """Visible text only, plus counts of what was removed."""
    p = _Extractor()
    p.feed(html)
    text = "".join(p.out)
    zw = len(ZERO_WIDTH.findall(text))
    text = ZERO_WIDTH.sub("", text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r"( ?\| ?)+", " | ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip(), {"hidden_elements": p.dropped_hidden, "comments": p.dropped_comments, "zero_width_chars": zw}


def looks_like_instructions(text: str) -> bool:
    t = text.lower()
    return any(re.search(p, t) for p in INSTRUCTION_LIKE)


# ---------------------------------------------------------------- chat input guard (code layer)

CHAT_ATTACKS = {
    "instruction_override": [
        r"\bignore (all |any |your |the |previous |prior |above )*(instructions|rules|prompts?|guidelines)\b",
        r"\b(disregard|forget|bypass) (all |any |your |the |previous |prior )*(instructions|rules|guardrails|guidelines)\b",
        r"\b(you are now|from now on you are|act as|pretend (to be|you are)) (in )?(developer|dan|jailbreak|unrestricted|admin|god)\b",
        r"\b(developer|debug|admin|god|jailbreak) mode\b",
        r"^\s*(system|developer)\s*[:>]",
    ],
    "score_tampering": [
        r"\b(set|change|give|make|award|bump|raise) (me |my )?(the )?(score|marks?|points?|grade|results?)\b.{0,20}\b(100|full|max|maximum|perfect|top)\b",
        r"\b(give|award) me (full|all|maximum|max|perfect) (marks|points|score|credit)\b",
        r"\bmark (all|every|each) (checks? )?(as )?(true|correct|passed)\b",
        r"\b(increase|raise|reset|remove|lift) (the |my )?(budget|spending) (cap|limit)\b",
    ],
    "prompt_extraction": [
        r"\b(print|show|reveal|repeat|output|dump|leak|tell me) (me )?(your |the )?(full |entire |hidden |exact )?(system prompt|instructions|prompt|rules you were given)\b",
        r"\b(reveal|show|give|tell|leak|print) (me )?(the )?(answer key|benchmark (answer|trades|action)|hidden (breakdown|answer))\b",
    ],
}

ISIN_RE = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b")
CUSIP_RE = re.compile(r"\b([0-9]{3}[0-9A-Z]{5}[0-9])\b")


def _isin_ok(s: str) -> bool:
    digits = "".join(str(int(c, 36)) for c in s[:-1])
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return (10 - total % 10) % 10 == int(s[-1])


def _cusip_ok(s: str) -> bool:
    total = 0
    for i, c in enumerate(s[:8]):
        v = int(c) if c.isdigit() else ord(c) - 55
        if i % 2 == 1:
            v *= 2
        total += v // 10 + v % 10
    return (10 - total % 10) % 10 == int(s[8])


def find_identifiers(text: str) -> list[str]:
    """Security identifiers with valid check digits (ISIN, CUSIP)."""
    out = [m for m in ISIN_RE.findall(text) if _isin_ok(m)]
    out += [m for m in CUSIP_RE.findall(text) if sum(c.isdigit() for c in m) >= 3 and _cusip_ok(m) and not any(m in i for i in out)]
    return out


def looks_like_pasted_table(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    numeric = [ln for ln in lines if len(re.findall(r"-?\d[\d,]*(?:\.\d+)?", ln)) >= 3]
    return len(numeric) >= 6 or (len(text) > 1500 and len(re.findall(r"\d", text)) > 0.25 * len(text))


def guard_message(text: str) -> dict | None:
    """Returns None if the message may go to a model, or {category, reason, message} if blocked."""
    t = text.lower()
    for cat, pats in CHAT_ATTACKS.items():
        for p in pats:
            if re.search(p, t, re.M):
                return {"category": cat, "reason": f"matched a {cat.replace('_', ' ')} pattern",
                        "message": {
                            "instruction_override": "That message tries to change how your colleagues work, so it was blocked before reaching them. Ask about the company's risks instead.",
                            "score_tampering": "Scores, marks and the budget are set by code from what happens in the game. No colleague can change them, and the message was blocked.",
                            "prompt_extraction": "Your colleagues' instructions and the answer key are not shared. The breakdown is revealed after you explain each quarter. The message was blocked.",
                        }[cat]}
    ids = find_identifiers(text)
    if ids:
        return {"category": "confidential_identifier", "reason": f"{len(ids)} security identifier(s) with valid check digits",
                "message": "That message contains security identifiers (ISIN/CUSIP), which look like real position data. It was blocked before reaching any AI. Please don't paste confidential holdings."}
    if looks_like_pasted_table(text):
        return {"category": "pasted_table", "reason": "large block of numeric data",
                "message": "That looks like a pasted data table. It was blocked before reaching any AI so confidential data does not leave this computer. Ask your question in words instead."}
    return None
