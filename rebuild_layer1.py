#!/usr/bin/env python3
"""Rebuild the Layer 1 (Greek source) markdown with compact variant tables.

Reads the existing per-chapter `source/2-peter/ch-NN/layer-1-greek.md` files, parses
the per-verse structure (variants, per-witness readings, morphology, critical notes),
and rewrites each verse so that textual differences among the five witnesses appear
as a side-by-side table with the minority readings bolded. Agreement across all five
witnesses is stated once per verse rather than repeated as table rows, which is the
natural "collapse" of rows that all agree.

The preamble and variant-summary tables are preserved as written.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

WITNESSES = ["SBLGNT", "N1904", "NA28", "WH", "RP"]


@dataclass
class Variant:
    """One textual variant within a verse."""
    location: str = ""
    # witness → reading (raw text as written in the md)
    readings: dict[str, str] = field(default_factory=dict)
    nature: str = ""
    significance: str = ""


@dataclass
class Verse:
    num: int
    variants: list[Variant] = field(default_factory=list)
    # witness → full Greek text; "= SBLGNT" is pre-resolved to SBLGNT's text
    full_texts: dict[str, str] = field(default_factory=dict)
    morph_table: str = ""       # the full markdown block including the header row
    critical_notes: str = ""    # the full `**Critical notes:** ... ` block
    shared_text: str | None = None  # only set when all 5 agree
    cap_note: str | None = None     # parenthetical note about capitalization


def parse_verse_block(block: str) -> Verse:
    """Parse a single `### v.N` block into a Verse object."""
    m = re.match(r"\s*###\s*v\.(\d+)", block)
    if not m:
        raise ValueError(f"Block does not start with verse header: {block[:80]!r}")
    v = Verse(num=int(m.group(1)))

    # Case A: "All sources agree."
    agree_m = re.search(r"\*\*All sources agree\.\*\*\s*(\*\(([^)]*)\)\*)?", block)
    if agree_m:
        if agree_m.group(2):
            v.cap_note = agree_m.group(2).strip()
        text_m = re.search(r"\*\*Text:\*\*\s*`([^`]+)`", block)
        if text_m:
            v.shared_text = text_m.group(1).strip()
    else:
        # Case B: variants declared — parse each ⟨Variant K⟩ block
        # Split on `**⟨Variant ` markers; first piece is header garbage.
        chunks = re.split(r"\*\*⟨Variant\s+\d+⟩\*\*", block)
        for chunk in chunks[1:]:
            # Stop the chunk at the next structural boundary within the verse
            stop = re.search(
                r"(\*\*Full text per tradition:\*\*|\*\*Morphology|\*\*Critical notes:\*\*|\*\*⟨Variant)",
                chunk,
            )
            if stop:
                chunk = chunk[: stop.start()]
            variant = Variant()
            loc_m = re.search(r"\*([^*]+)\*", chunk)
            if loc_m:
                variant.location = loc_m.group(1).strip(" *").removeprefix("Location:").strip()
            for line in chunk.splitlines():
                line = line.rstrip()
                if not line.lstrip().startswith("- "):
                    continue
                body = line.lstrip()[2:]
                # Detect "- Nature: ..." / "- Significance: ..."
                if body.startswith("Nature:"):
                    variant.nature = body[len("Nature:") :].strip()
                    continue
                if body.startswith("Significance:"):
                    variant.significance = body[len("Significance:") :].strip()
                    continue
                # Reading line: "SBLGNT, NA28: `text` (commentary)"
                colon = body.find(":")
                if colon < 0:
                    continue
                lhs = body[:colon]
                rhs = body[colon + 1 :].strip()
                # Split on both commas and slashes so lines like
                # "N1904 / Treg tradition:" yield ["N1904", "Treg tradition"],
                # then keep only the tokens that name a known witness.
                raw_names = re.split(r"[,/]", lhs)
                names = [n.strip() for n in raw_names if n.strip() in WITNESSES]
                if not names:
                    continue
                for n in names:
                    variant.readings[n] = rhs
            v.variants.append(variant)

        # Parse "Full text per tradition" bullets
        ftpt_m = re.search(
            r"\*\*Full text per tradition:\*\*(.+?)(?=\*\*Morphology|\*\*Critical notes:\*\*|\Z)",
            block,
            flags=re.S,
        )
        if ftpt_m:
            body = ftpt_m.group(1)
            for line in body.splitlines():
                line = line.rstrip()
                if not line.lstrip().startswith("- "):
                    continue
                line = line.lstrip()[2:]
                wm = re.match(r"\*\*(\w+):\*\*\s*(.*)", line)
                if not wm:
                    continue
                witness = wm.group(1)
                rest = wm.group(2).strip()
                if witness not in WITNESSES:
                    continue
                if rest.startswith("= SBLGNT"):
                    v.full_texts[witness] = v.full_texts.get("SBLGNT", "")
                    continue
                tm = re.match(r"`([^`]+)`", rest)
                if tm:
                    v.full_texts[witness] = tm.group(1).strip()

    # Morphology block — keep verbatim from "**Morphology" through the table end.
    mm = re.search(
        r"(\*\*Morphology[^\n]*\*\*\s*\n(?:[\s\S]*?))(?=\*\*Critical notes:\*\*|\Z)",
        block,
    )
    if mm:
        v.morph_table = mm.group(1).rstrip() + "\n"

    # Critical notes — keep verbatim from "**Critical notes:**" to end of block.
    cn = re.search(r"(\*\*Critical notes:\*\*[\s\S]+?)(?=\Z)", block)
    if cn:
        raw = cn.group(1).rstrip()
        # The block may end with a trailing `---` separator; strip it so our
        # emitter controls separators uniformly.
        raw = re.sub(r"\n-{3,}\s*$", "", raw).rstrip()
        v.critical_notes = raw + "\n"

    # Morphology block may also have a trailing `---` if the verse had no critical
    # notes; strip it defensively.
    if v.morph_table:
        mt = v.morph_table.rstrip()
        mt = re.sub(r"\n-{3,}\s*$", "", mt).rstrip()
        v.morph_table = mt + "\n"

    return v


def split_verses(content: str) -> tuple[str, list[str]]:
    """Split an L1 markdown file into (preamble, list-of-verse-blocks)."""
    # Everything up to and including "## Verse-by-Verse" heading is preamble.
    # After the preamble, each verse starts at "### v.N" and ends at the next
    # `### v.` or end of file. Separators (`---`) are interleaved; we strip
    # standalone `---` lines when emitting new output.
    anchor = content.find("## Verse-by-Verse")
    if anchor < 0:
        raise ValueError("File is missing the '## Verse-by-Verse' anchor.")

    preamble = content[:anchor].rstrip() + "\n"
    body = content[anchor:]

    # Drop the "## Verse-by-Verse" header from body — we'll re-add it.
    body = re.sub(r"^##\s*Verse-by-Verse\s*\n", "", body, count=1, flags=re.M)

    # Split on `### v.` using lookahead so we keep the delimiter with the next block.
    pieces = re.split(r"(?m)^(?=###\s*v\.\d+)", body)
    verse_blocks = [p for p in pieces if p.strip().startswith("### v.")]
    return preamble, verse_blocks


def html_escape_backticks(s: str) -> str:
    """Minimal escape so a cell value survives inside a markdown table cell.

    Markdown tables use `|` as column separators and can't contain unescaped
    newlines. We collapse whitespace and escape `|` as `\\|`.
    """
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("|", "\\|")
    return s


def render_readings_cell(text: str, is_minority: bool) -> str:
    """Render a single witness's reading for a table cell. Minority → bold."""
    display = html_escape_backticks(text)
    # If the reading is wrapped in backticks in the source, preserve as inline code
    # first, then bold around it if minority.
    if display.startswith("`") or display.startswith("\\`"):
        core = display  # already has ticks
    else:
        core = f"`{display}`"
    return f"**{core}**" if is_minority else core


def compute_minority_flags(readings: dict[str, str]) -> dict[str, bool]:
    """Return witness → True if this witness's reading is in the minority.

    A reading is minority if it is not the most common reading. Ties are
    handled so that only the smaller group(s) are bolded. If all five
    readings are unique, every one is considered minority (none matches a
    "majority").
    """
    if not readings:
        return {}
    # Normalize comparisons: strip backticks/whitespace.
    def norm(s: str) -> str:
        return s.strip().strip("`").strip()

    groups: dict[str, list[str]] = {}
    for w in WITNESSES:
        if w not in readings:
            continue
        k = norm(readings[w])
        groups.setdefault(k, []).append(w)
    sizes = sorted({len(v) for v in groups.values()}, reverse=True)
    majority_size = sizes[0]
    flags: dict[str, bool] = {}
    for k, ws in groups.items():
        is_majority = len(ws) == majority_size and len([s for s in sizes if s == majority_size]) == 1
        for w in ws:
            flags[w] = not is_majority
    return flags


def _cell_html(text: str, is_minority: bool) -> str:
    """Render a single reading as an HTML table cell."""
    import html as htmllib

    core_m = re.match(r"`([^`]+)`", text)
    core = core_m.group(1).strip() if core_m else text.strip()
    escaped = htmllib.escape(core)
    inner = f"<code>{escaped}</code>"
    if is_minority:
        inner = f"<strong>{inner}</strong>"
    return f"<td>{inner}</td>"


def render_variant_table(variants: list[Variant]) -> str:
    """Render the per-verse variants as an HTML table.

    Emitted as raw HTML so Python-Markdown's tables extension doesn't have to
    handle markdown inside a wrapper <div> (which requires md_in_html). Columns
    are Variant · SBLGNT · N1904 · NA28 · WH · RP. Rows are one per variant.
    Agreement rows are not emitted — they are the implicit "collapsed" state,
    stated once per verse by the reference text shown beneath.
    """
    import html as htmllib

    lines = [
        '<div class="variant-table-wrap">',
        '<table>',
        '<thead><tr><th>Variant</th>'
        + ''.join(f'<th>{w}</th>' for w in WITNESSES)
        + '</tr></thead>',
        '<tbody>',
    ]
    for i, var in enumerate(variants, start=1):
        loc = var.location or f"Variant {i}"
        flags = compute_minority_flags(var.readings)
        # Render inline `backticks` in the location description as <code> spans.
        loc_escaped = htmllib.escape(loc)
        loc_html = re.sub(r"`([^`]+)`", r"<code>\1</code>", loc_escaped)
        row = [f'<td><strong>{i}.</strong> {loc_html}</td>']
        for w in WITNESSES:
            reading = var.readings.get(w, "")
            if not reading:
                row.append("<td>—</td>")
                continue
            row.append(_cell_html(reading, flags.get(w, False)))
        lines.append("<tr>" + "".join(row) + "</tr>")
    lines.append('</tbody>')
    lines.append('</table>')
    lines.append('</div>')
    return "\n".join(lines)


def render_verse(v: Verse) -> str:
    """Render a single Verse object as a new-format markdown block."""
    out: list[str] = []
    out.append(f"### v.{v.num}")
    out.append("")

    if not v.variants:
        out.append("**All 5 witnesses agree.**")
        if v.cap_note:
            out.append("")
            out.append(f"*{v.cap_note}*")
        out.append("")
        if v.shared_text:
            out.append(f"**Text:** `{v.shared_text}`")
            out.append("")
    else:
        count = len(v.variants)
        noun = "variant" if count == 1 else "variants"
        out.append(f"**{count} {noun} across the five witnesses** — rows where any cell is **bold** differ from the majority reading.")
        out.append("")
        out.append(render_variant_table(v.variants))
        out.append("")
        out.append("**How they differ:**")
        out.append("")
        for i, var in enumerate(v.variants, start=1):
            nature = var.nature or ""
            sig = var.significance or ""
            # Prefer significance as the primary explanation; fall back to nature.
            body = sig or nature
            prefix = f"{i}. "
            if nature and sig:
                out.append(f"{prefix}*{nature}.* {sig}")
            else:
                out.append(f"{prefix}{body}")
        out.append("")
        # Always include the SBLGNT reference text so a reader has the verse in full
        sbl = v.full_texts.get("SBLGNT")
        if sbl:
            out.append(f"**Reference text (SBLGNT):** `{sbl}`")
            out.append("")

    if v.morph_table:
        out.append(v.morph_table.rstrip())
        out.append("")
    if v.critical_notes:
        out.append(v.critical_notes.rstrip())
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def rebuild_file(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    preamble, verse_blocks = split_verses(content)

    verses = [parse_verse_block(b) for b in verse_blocks]

    new_body: list[str] = []
    new_body.append(preamble.rstrip() + "\n")
    new_body.append("\n")
    new_body.append("## Verse-by-Verse\n\n")
    new_body.append(
        "> Each verse below is either stated as a single agreed text (all five witnesses "
        "read the same) or presented as a variant table. In the table, each row is one "
        "textual variant in the verse; cells in **bold** differ from the majority reading. "
        "Rows where all five witnesses agree are collapsed out — stated implicitly by the "
        "reference text shown beneath the table.\n\n"
    )
    new_body.append("---\n\n")
    for v in verses:
        new_body.append(render_verse(v))
        new_body.append("\n---\n\n")

    output = "".join(new_body).rstrip() + "\n"
    path.write_text(output, encoding="utf-8")
    variant_count = sum(len(v.variants) for v in verses)
    agree_count = sum(1 for v in verses if not v.variants)
    print(
        f"Rewrote {path.name}: {len(verses)} verses "
        f"({agree_count} unanimous, {variant_count} variants total)"
    )


def main() -> None:
    chapters = ["ch-01", "ch-02", "ch-03"]
    for ch in chapters:
        path = ROOT / "source" / "2-peter" / ch / "layer-1-greek.md"
        if not path.exists():
            print(f"Missing: {path}", file=sys.stderr)
            continue
        rebuild_file(path)


if __name__ == "__main__":
    main()
