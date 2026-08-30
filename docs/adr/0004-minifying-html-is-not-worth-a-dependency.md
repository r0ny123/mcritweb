# Minifying HTML is not worth a dependency

---
status: accepted — measured 2026-08-30
---

Issue #48 asks for three things: `{%- -%}` whitespace control in Jinja, an HTML
minifier, and a prettifier in debug mode. **The first two should not be done**, and the
numbers are the reason rather than a preference.

Whitespace-collapsing every rendered page — an *upper bound* on what either `{%- -%}` or
a minifier could save — measured against the offline corpus:

| page | raw HTML | ws-stripped | saving | gzip raw | gzip min | **gzip saving** |
|---|---|---|---|---|---|---|
| `/` | 32,880 | 28,432 | 13.5% | 6,795 | 6,359 | **436 B** |
| `/data/jobs` | 49,175 | 41,384 | 15.8% | 8,907 | 8,145 | **762 B** |
| `/data/result/…` (1vsN) | 206,344 | 142,401 | 31.0% | 12,340 | 11,176 | **1,164 B** |
| `/explore/samples` | 61,360 | 49,797 | 18.8% | 9,808 | 9,029 | **779 B** |
| **13 pages** | **1,155,307** | **910,958** | **21.2%** | **129,019** | **120,401** | **8,618 B** |

Against what a page actually ships. Vendored assets loaded unconditionally by
`base.html` total **1,184,774 bytes raw / 276,792 gzipped**. Cold load in headless
Chromium, counting every response body:

```
index        doc 32,880 | script 1,141,444 (n=8) | css 396,598 (n=8) | font 150,472 | img 18,876
             TOTAL 1,740,270 — html share 1.9%
result 1vsN  doc 206,344 | script 1,141,444 | css 396,598 | font 175,568 | img 22,362
             TOTAL 1,942,316 — html share 10.6%
```

So on the heaviest page in the application, a minifier saves **1.1 KB gzipped against a
1.9 MB first load** — 0.06%. On light pages, 400–800 bytes.

The `{%- -%}` variant is worse than merely not worth it: it means editing ~40 templates,
it silently changes rendering inside `<pre>` (`column_table.html`'s error block is
`<pre><code>`), and it makes every future template diff noisier.

## Consequences

The payload problem in this application is **1.14 MB of vendored JavaScript on every
page**, not markup whitespace. `jquery-ui.js` alone is 529 KB and is used for
`$().sortable()` on the cross-compare page and for `autocomplete.js`. Issue #63 is the
right shape for that — loading a library only on the pages that use it — and it is worth
roughly 100× what minification is.

The third bullet, a prettifier in debug mode, is a separate and much smaller question
about developer experience, not payload. It is not decided here.

## Outcome

Recommend closing the minify and `{%- -%}` halves of #48 as measured-not-worth-doing, and
opening the vendored-JS weight as its own issue if it is not already covered by #63.
