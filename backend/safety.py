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
