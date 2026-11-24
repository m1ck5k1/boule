"""Render a third party's markup safely — a whitelist, not a blocklist.

CRS summaries arrive with HTML in them (`<p>`, `<strong>`, `<em>`). "Verbatim" describes
CRS's WORDS; it is not a licence to inject a third party's markup into our pages. So the
allowed tag set is tiny, every attribute is dropped, and anything unrecognised loses its
markup and survives as escaped text.

Kept in its own module with no imports of its own, so the web tier can use it without
dragging the Congress.gov client (and its dotenv loading) into the server process.
"""
from __future__ import annotations

import html
import re

ALLOWED = frozenset({"p", "strong", "em", "b", "i", "br", "ul", "ol", "li"})

_TAG = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]*)(\s[^>]*)?>")


def sanitize(raw: str) -> str:
    """Keep the whitelisted tags, escape everything else. Attributes never survive.

    Entities are resolved to their characters first, then escaped: CRS writes `&nbsp;` as an
    entity, and escaping it without unescaping would print the entity itself on the page.
    Unescaping first is still safe — `&lt;script&gt;` becomes text, and is escaped back to
    text, so nothing unescaping produces can ever become a tag.
    """
    out: list[str] = []
    pos = 0
    for m in _TAG.finditer(raw or ""):
        out.append(html.escape(html.unescape(raw[pos:m.start()])))
        name = m.group(1).lower()
        if name in ALLOWED:
            out.append(f"</{name}>" if m.group(0).startswith("</") else f"<{name}>")
        pos = m.end()
    out.append(html.escape(html.unescape(raw[pos:])))
    return "".join(out)
