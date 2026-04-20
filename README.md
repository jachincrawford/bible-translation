# Bible Translation — Public Site

A 7-layer English translation of the Bible, published as a simple static site.

**Live site:** https://jachincrawford.github.io/bible-translation/

## Layer architecture

| Layer | Name | Philosophy | Comparable to |
|-------|------|------------|---------------|
| 1 | Original Greek / Hebrew | Source text only | NA28 / BHS |
| 2 | Word-for-Word | Mechanical gloss | Interlinear |
| 3 | Grammatical English | Grammar-normalized, no interpretation | Literal+ |
| 4 | Phrase-for-Phrase | Phrase-level equivalence | NASB / ESV |
| 5 | Thought-for-Thought | Functional equivalence | NIV / CSB |
| 6 | Paraphrase | Plain-language meaning | The Message |
| 7 | Commentary | Lexical, grammatical-historical, discourse, literary, canonical, theological, church-historical, devotional | — |

## Repository layout

```
source/          markdown source for each book/chapter/layer
docs/            generated static HTML site (GitHub Pages root)
build.py         static site generator
templates/       HTML templates and CSS
```

## Rebuilding the site

```
python3 build.py
```

Regenerates everything under `docs/` from `source/`.

## License

- Translation text and commentary: **CC BY 4.0** (see [LICENSE](LICENSE))
- Source code (`build.py`, templates): **MIT** (see [LICENSE](LICENSE))
- Underlying biblical source texts retain the licenses of their publishers.

## Status

- **2 Peter** — chapters 1–3 published
- Genesis, John, Acts — not yet published to this site
