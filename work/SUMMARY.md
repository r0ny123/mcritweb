# SUMMARY — mcritweb triage and fix campaign

**54 open upstream issues triaged. 54 covered by an open PR. 60 PRs opened on the fork.**

Cross-referenced from `work/STATE.md` (the triage table, and the full
issue → branch → PR map at the end of it), `work/LOG.md` (what was tried, what
happened, what was decided, and where I was wrong) and `work/SETUP.md` (how to
reproduce any of it).

All PRs are against `r0ny123/mcritweb`, base `master`. **Never upstream.**

---

## Where to start reading

**Merge `#9` first.** Every unit job on every branch was failing with `No module named
pytest` — the suite had not run in CI since `mcrit` moved pytest behind its `dev` extra.
It blocks everything else.

Then the two that a deployment would want soonest, both found in passing rather than
triaged:

- **[#58](https://github.com/r0ny123/mcritweb/pull/58) — a visitor chooses where
  `/analyze/query` writes its upload.** The filename came straight from the SMDA report's
  own `sha256` field, which nothing validates, and was joined into a path. Reproduced
  against `df53db9`: a report declaring `"sha256": "../../../PLANTED"` returns 202 and
  puts 303 bytes of attacker-chosen content outside the instance directory entirely.
  `@visitor_required` is the lowest role this application has.
- **[#37](https://github.com/r0ny123/mcritweb/pull/37) — promoting a query could import an
  attacker's sample.** The `.smda` integrity check compared the stored file against a
  field *inside that file*. Since `analyze.query` files uploads under the name the report
  declares, a visitor could overwrite a contributor's stored query; the contributor's next
  "Promote to sample" click then put the planted report — with the attacker's family and
  filename — into the corpus. Now checked against `Job.sha256`, the hash the backend
  recorded for the payload the job actually ran on.

---

## What the campaign found, beyond the issues themselves

**Nine tests that passed with the code they guarded deleted.** Each was reproduced by
reverting the code, not by reading it:

| PR | what could be deleted with the suite green |
|---|---|
| #35 | `with_xcfg=True` — without it *every* function page says "no control flow information" in production |
| #45 | the clipboard fix reverted to the exact issue #80 bug |
| #45 | the entire client-side sorting script |
| #43 | both atomic writes reverted to in-place — two tests were *named* for atomicity and could not see it |
| #44 | the newest-first job order, scrambled two ways at once |
| #50 | `unique_match_known=False` dropped from both vs call sites — adds a whole column to the 1-vs-1 page |
| #41 | the search-page deserialisation the test names in its docstring |
| #38 | the cap's flash message, satisfied by static page prose |
| #37 | the non-query-job guard |

**A live XSS sink held shut by two unrelated bugs.** `main.js:2733-2738` assigns a
dot-graph node label into `innerHTML`, and those labels carry `apirefs` — import names
read out of the analysed binary, interpolated by smda with no escaping. It does not fire
today only because the handler throws two lines earlier on one page and the target ids do
not exist on the other. **Fixing either of those "obvious" bugs arms it.** Recorded on
PR #42; not touched, because touching it means rewriting the tooltip.

**Claims of my own that were wrong**, each re-measured and corrected in place — the full
list is in `work/LOG.md`. The ones that mattered: "344 of 609 functions raise through loop
detection" (**0** raise); "no other integer rendering is on a score" (**six**, one of them
a default-visible column); "the unfiltered page is unchanged down to the rendered string"
(it reindented every page); "the rendered rows are byte-identical" (not above the sign
bit); and PR #43's "-77%" reading as work saved when it is page latency and the total is
flat.

---

## How each PR was built

Same shape throughout: reproduce before fixing, smallest viable change, failing test
first where practical, then a hostile self-review round repeated until a full pass finds
nothing. Every test added or changed was **mutation-checked** — break the code it guards,
confirm it fails, restore. Full suite and `ruff check .` before every push, with exit
codes captured explicitly rather than through a pipe.

**Where a fix was not this repository's to make, it got an ADR instead of a patch** —
`docs/adr/0003` through `0008`, for issues #72, #48, #47, #59, #37 and #57. Each names the
upstream code and the version it was read against, so the conclusion can be re-checked
rather than re-derived.

---

## Honest limits, stated once

- **Nothing was exercised against a real MCRIT backend or MongoDB.** Neither is available
  in this environment. Everything runs against the captured corpus in `tests/fixtures/`
  behind the `MCRIT_CLIENT_FACTORY` seam, plus an offline dev harness and headless
  Chromium. Anything past login is "not reproduced against a real backend" — that is the
  normal state here, and `work/STATE.md` says so per issue.
- **`tests/fixtures/families.json` was reconstructed, not captured** (PR #45). Exact by
  construction and verified against the installed backend's `FamilyResource.on_get`, but
  the next real `regenerate.py` run is what confirms it end to end.
- **`tests/testBrowser.py` skips in CI** (PR #45), which installs no browser. Both skip
  paths verified to exit 0. Adding playwright to `requirements.txt` is a maintainer
  decision, not a review fix.
- **Two deliberate behaviour changes**, both flagged on their PRs and both reversible in
  one line: `SAMPLE_DUMP.BIN` is now recognised as a dump (#39), and scores of 99.5 now
  render `100` (#46).
- **`os.replace` across `cache/incomplete` → `cache/diagrams`** (#43) is a rename only
  while both sit on one filesystem. Previously guaranteed; now merely true unless someone
  mounts a cache subdirectory separately. Documented, not tested — I cannot create a
  second filesystem here.

---

## Guardrails held

No force-push, no rewritten shared history, no commits to `master`. No PR against upstream
`fkie-cad/mcritweb`. No secrets or `.env` content committed — checked mechanically before
each push. **No test was deleted or disabled to make a suite pass**; where a test was
wrong it was rewritten in place and the rewrite mutation-checked. Nothing is claimed fixed
or reproduced that was not run, with the output pasted into the log or the PR.
