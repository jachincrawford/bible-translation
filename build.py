#!/usr/bin/env python3
"""Static site generator for the bible-translation repo.

Reads source/<book-slug>/ch-NN/layer-*.md and writes docs/ as a static site
with breadcrumbs and prev/next chapter navigation.
"""
from __future__ import annotations

import html
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import markdown

ROOT = Path(__file__).parent.resolve()
SRC = ROOT / "source"
OUT = ROOT / "docs"
TPL = ROOT / "templates"

SITE_TITLE = "Bible Translation"
SITE_TAGLINE = "A 7-layer English translation, published openly"
SITE_BASE = "/bible-translation"  # GitHub Pages project path

# Ordered layer metadata. Keys match source filename stems.
LAYERS = [
    ("layer-1-greek",                  "L1",  "Original Greek",             "Source text only — no interpretation"),
    ("layer-2-word-for-word",          "L2",  "Word-for-Word",              "Mechanical gloss, interlinear-style"),
    ("layer-3-grammatical-english",    "L3",  "Grammatical English",        "Grammar-normalized, no interpretation"),
    ("layer-4-phrase-for-phrase",      "L4",  "Phrase-for-Phrase",          "Phrase-level equivalence (NASB/ESV style)"),
    ("layer-5-thought-for-thought",    "L5",  "Thought-for-Thought",        "Functional equivalence (NIV/CSB style)"),
    ("layer-6-paraphrase",             "L6",  "Paraphrase",                 "Plain-language meaning — not Scripture"),
    ("layer-7a-lexical-semantic",      "L7A", "Lexical-Semantic",           "Word meaning and semantic range"),
    ("layer-7b-grammatical-historical","L7B", "Grammatical-Historical",     "Authorial intent in context"),
    ("layer-7c-discourse",             "L7C", "Discourse Analysis",         "Argument and narrative structure"),
    ("layer-7d-literary-genre",        "L7D", "Literary / Genre",           "Devices, rhetoric, style"),
    ("layer-7e-canonical",             "L7E", "Canonical",                  "Scripture interprets Scripture"),
    ("layer-7f-theological",           "L7F", "Theological",                "Doctrinal synthesis"),
    ("layer-7g-historical-church",     "L7G", "Historical Church",          "Patristic through modern voices"),
    ("layer-7h-spiritual-devotional",  "L7H", "Spiritual / Devotional",     "Formation and prayer"),
]
LAYER_BY_STEM = {stem: (code, name, sub) for stem, code, name, sub in LAYERS}

# Ordered list of books. Add entries as more books are published.
BOOKS = [
    {"slug": "2-peter", "title": "2 Peter", "chapter_count": 3},
]


@dataclass
class Crumb:
    label: str
    href: str | None  # None = current page (no link)


def asset(path: str) -> str:
    """Return a site-base-aware path for assets/links."""
    if path.startswith("/"):
        return SITE_BASE + path
    return SITE_BASE + "/" + path


def page(title: str, crumbs: list[Crumb], body: str, extra_head: str = "") -> str:
    crumb_html_parts = []
    for i, c in enumerate(crumbs):
        if i > 0:
            crumb_html_parts.append('<span class="sep">›</span>')
        if c.href:
            crumb_html_parts.append(f'<a href="{html.escape(c.href)}">{html.escape(c.label)}</a>')
        else:
            crumb_html_parts.append(f'<span>{html.escape(c.label)}</span>')
    crumbs_html = "".join(crumb_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — {html.escape(SITE_TITLE)}</title>
<link rel="stylesheet" href="{asset('/assets/style.css')}">
{extra_head}
</head>
<body>
<header class="site">
  <nav class="crumbs">{crumbs_html}</nav>
</header>
<main>
{body}
</main>
<footer class="site">
  <p>{html.escape(SITE_TAGLINE)} · Translation text licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.
  <a href="https://github.com/jachincrawford/bible-translation">Source on GitHub</a>.</p>
</footer>
</body>
</html>
"""


def render_markdown(text: str) -> str:
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
    return md.convert(text)


def strip_leading_h1(md_text: str) -> tuple[str, str | None]:
    """If the markdown starts with an H1, strip it and return (remaining, h1_text)."""
    lines = md_text.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        m = re.match(r"^#\s+(.*)$", stripped)
        if m:
            return "\n".join(lines[i + 1 :]).lstrip(), m.group(1).strip()
        return md_text, None
    return md_text, None


def ch_slug(n: int) -> str:
    return f"ch-{n:02d}"


def book_crumb(book: dict, as_link: bool) -> Crumb:
    return Crumb(book["title"], asset(f"/{book['slug']}/") if as_link else None)


def home_crumb(as_link: bool) -> Crumb:
    return Crumb("Home", asset("/") if as_link else None)


def build_home() -> None:
    cards = []
    for b in BOOKS:
        b_slug = b["slug"]
        b_title = b["title"]
        b_count = b["chapter_count"]
        href = asset(f"/{b_slug}/")
        cards.append(
            f'<li><a href="{href}">'
            f'<span class="label">Book</span>'
            f'<span class="title">{html.escape(b_title)}</span>'
            f'<span class="sub">{b_count} chapters</span>'
            f"</a></li>"
        )
    cards_html = "\n".join(cards)

    body = f"""
<h1>{html.escape(SITE_TITLE)}</h1>
<p>A seven-layer English translation of the Bible, from the original Greek and Hebrew
through mechanical gloss, phrase-for-phrase, thought-for-thought, paraphrase, and
multi-stream commentary. Every page is a single chapter in a single layer — pick a
book to begin.</p>

<h2>Books available</h2>
<ul class="cards">
{cards_html}
</ul>

<h2>The seven layers</h2>
<ol>
<li><strong>Original Greek / Hebrew</strong> — source text only.</li>
<li><strong>Word-for-Word</strong> — mechanical gloss.</li>
<li><strong>Grammatical English</strong> — grammar-normalized, no interpretation.</li>
<li><strong>Phrase-for-Phrase</strong> — phrase-level equivalence (NASB/ESV style).</li>
<li><strong>Thought-for-Thought</strong> — functional equivalence (NIV/CSB style).</li>
<li><strong>Paraphrase</strong> — plain-language meaning (labeled not-Scripture).</li>
<li><strong>Commentary (7A–7H)</strong> — lexical, grammatical-historical, discourse,
literary, canonical, theological, church-historical, devotional streams.</li>
</ol>
"""
    write(OUT / "index.html", page(SITE_TITLE, [home_crumb(False)], body))


def build_book(book: dict) -> None:
    chapters = []
    slug = book["slug"]
    title = book["title"]
    for n in range(1, book["chapter_count"] + 1):
        href = asset(f"/{slug}/{ch_slug(n)}/")
        chapters.append(
            f'<li><a href="{href}">'
            f'<span class="label">Chapter {n}</span>'
            f'<span class="title">{html.escape(title)} {n}</span>'
            f"</a></li>"
        )
    chapter_list = "\n".join(chapters)
    body = f"""
<h1>{html.escape(title)}</h1>
<p>Pick a chapter to see all seven translation layers.</p>
<ul class="cards">
{chapter_list}
</ul>
"""
    crumbs = [home_crumb(True), book_crumb(book, False)]
    write(OUT / slug / "index.html", page(title, crumbs, body))


def build_chapter_index(book: dict, ch: int) -> None:
    """Landing page for a chapter listing all available layers."""
    slug = book["slug"]
    title = book["title"]
    base = SRC / slug / ch_slug(ch)
    layer_cards = []
    for stem, code, name, sub in LAYERS:
        fp = base / f"{stem}.md"
        if not fp.exists():
            continue
        href = asset(f"/{slug}/{ch_slug(ch)}/{stem}.html")
        layer_cards.append(
            f'<li><a href="{href}">'
            f'<span class="label">{html.escape(code)}</span>'
            f'<span class="title">{html.escape(name)}</span>'
            f'<span class="sub">{html.escape(sub)}</span>'
            f"</a></li>"
        )

    prev_next = render_prev_next(book, ch)
    layer_list = "\n".join(layer_cards)

    body = f"""
<h1>{html.escape(title)} {ch}</h1>
<p>Seven layers, each in its own lane. Layers 1–3 carry no interpretation. Layers 4–5
are English-language translations of increasing functional adaptation. Layer 6 is an
explanatory paraphrase, not Scripture. Layer 7 is commentary in eight streams.</p>

<ul class="cards layer-grid">
{layer_list}
</ul>

{prev_next}
"""
    crumbs = [home_crumb(True), book_crumb(book, True), Crumb(f"Chapter {ch}", None)]
    out = OUT / slug / ch_slug(ch) / "index.html"
    write(out, page(f"{title} {ch}", crumbs, body))


def build_layer_page(book: dict, ch: int, stem: str, code: str, name: str) -> None:
    slug = book["slug"]
    title = book["title"]
    base = SRC / slug / ch_slug(ch)
    md_path = base / f"{stem}.md"
    md_text = md_path.read_text(encoding="utf-8")
    md_body, _h1 = strip_leading_h1(md_text)
    body_html = render_markdown(md_body)

    prev_next = render_prev_next(book, ch, stem=stem, code=code, name=name)

    body = f"""
<h1>{html.escape(title)} {ch} <small style="color:#888;font-size:0.55em;">— {html.escape(code)} {html.escape(name)}</small></h1>
{body_html}
{prev_next}
"""
    crumbs = [
        home_crumb(True),
        book_crumb(book, True),
        Crumb(f"Chapter {ch}", asset(f"/{slug}/{ch_slug(ch)}/")),
        Crumb(f"{code} {name}", None),
    ]
    out = OUT / slug / ch_slug(ch) / f"{stem}.html"
    write(out, page(f"{title} {ch} — {name}", crumbs, body))


def render_prev_next(book: dict, ch: int, stem: str | None = None,
                     code: str | None = None, name: str | None = None) -> str:
    """Prev/next by chapter. If on a layer page, link to same layer in adjacent chapter
    when it exists; otherwise link to adjacent chapter index."""
    parts = ['<nav class="prevnext">']

    # Previous
    if ch > 1:
        prev_ch = ch - 1
        prev_href = _layer_or_chapter_href(book, prev_ch, stem)
        parts.append(
            f'<a class="prev" href="{prev_href}">'
            f'<span class="dir">← Previous</span>'
            f'<span class="label">{html.escape(book["title"])} {prev_ch}</span>'
            f"</a>"
        )
    else:
        parts.append('<span class="placeholder">Start of book</span>')

    # Next
    if ch < book["chapter_count"]:
        next_ch = ch + 1
        next_href = _layer_or_chapter_href(book, next_ch, stem)
        parts.append(
            f'<a class="next" href="{next_href}">'
            f'<span class="dir">Next →</span>'
            f'<span class="label">{html.escape(book["title"])} {next_ch}</span>'
            f"</a>"
        )
    else:
        parts.append('<span class="placeholder">End of book</span>')

    parts.append("</nav>")
    return "\n".join(parts)


def _layer_or_chapter_href(book: dict, ch: int, stem: str | None) -> str:
    if stem is not None:
        candidate = SRC / book["slug"] / ch_slug(ch) / f"{stem}.md"
        if candidate.exists():
            return asset(f"/{book['slug']}/{ch_slug(ch)}/{stem}.html")
    return asset(f"/{book['slug']}/{ch_slug(ch)}/")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def copy_assets() -> None:
    assets_dir = OUT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(TPL / "style.css", assets_dir / "style.css")


def main() -> None:
    if OUT.exists():
        for child in OUT.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    OUT.mkdir(parents=True, exist_ok=True)

    # Required for GitHub Pages to skip Jekyll processing.
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    copy_assets()
    build_home()

    page_count = 2  # home + .nojekyll
    for book in BOOKS:
        build_book(book)
        page_count += 1
        for ch in range(1, book["chapter_count"] + 1):
            build_chapter_index(book, ch)
            page_count += 1
            base = SRC / book["slug"] / ch_slug(ch)
            for stem, code, name, _sub in LAYERS:
                if (base / f"{stem}.md").exists():
                    build_layer_page(book, ch, stem, code, name)
                    page_count += 1

    print(f"Built site at {OUT} ({page_count} files).")


if __name__ == "__main__":
    main()
