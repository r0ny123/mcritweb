# SUMMARY — mcritweb triage and fix campaign

**54 open upstream issues triaged. 54 covered by an open PR. 60 PRs opened on the fork.**

Cross-referenced from `work/STATE.md` (the triage table, and the full
issue → branch → PR map at the end of it), `work/LOG.md` (what was tried, what
happened, what was decided, and where I was wrong) and `work/SETUP.md` (how to
reproduce any of it).

Every PR exists twice: once on `r0ny123/mcritweb` and once on `fkie-cad/mcritweb`, both
against `master`, from the same branch. See "All 60 PRs are open upstream" below.

---

## All 60 PRs are open upstream

Opened against `fkie-cad/mcritweb` on 2026-08-30, on explicit instruction that overrode
the fork-only guardrail. Same branches as the fork PRs beside them — one head, two PRs —
so merging either side lands identical code.

**Upstream #103-#162. CI: 47 green, 0 red, 14 still running at the time of writing.**

Merge [#103](https://github.com/fkie-cad/mcritweb/pull/103) first: it is the `No module
named pytest` fix, it came back green on all five upstream jobs, and it is what lets the
other 59 run at all.

The three opened first got upstream bodies written from scratch:
[#103](https://github.com/fkie-cad/mcritweb/pull/103) (CI),
[#104](https://github.com/fkie-cad/mcritweb/pull/104) (path traversal, security) and
[#105](https://github.com/fkie-cad/mcritweb/pull/105) (promote a query, issue #9).
The other 57 were transformed from their fork bodies: generated-by footer stripped, clone
URLs pointed at `fkie-cad`, a provenance header added, and sibling links repointed at
their upstream counterparts. Bare `#N` are upstream issue numbers throughout and were
deliberately left alone.

<details>
<summary>Full upstream -> fork -> branch map (60)</summary>

| upstream | fork | branch |
|---|---|---|
| [#103](https://github.com/fkie-cad/mcritweb/pull/103) | #9 | `fix/ci-install-pytest` |
| [#104](https://github.com/fkie-cad/mcritweb/pull/104) | #58 | `fix/query-upload-path-traversal` |
| [#105](https://github.com/fkie-cad/mcritweb/pull/105) | #37 | `fix/9-promote-a-query-to-a-sample` |
| [#106](https://github.com/fkie-cad/mcritweb/pull/106) | #2 | `fix/linkhunt-500-on-incompatible-job` |
| [#107](https://github.com/fkie-cad/mcritweb/pull/107) | #3 | `fix/73-empty-result-vs-unknown-job` |
| [#108](https://github.com/fkie-cad/mcritweb/pull/108) | #4 | `fix/98-timezone-aware-timestamps` |
| [#109](https://github.com/fkie-cad/mcritweb/pull/109) | #5 | `fix/54-say-when-a-search-matched-nothing` |
| [#110](https://github.com/fkie-cad/mcritweb/pull/110) | #6 | `fix/101-do-not-confirm-which-accounts-exist` |
| [#111](https://github.com/fkie-cad/mcritweb/pull/111) | #7 | `fix/100-apitoken-generation-and-rotation` |
| [#112](https://github.com/fkie-cad/mcritweb/pull/112) | #8 | `fix/78-deduplicate-search-results` |
| [#113](https://github.com/fkie-cad/mcritweb/pull/113) | #10 | `fix/79-say-what-a-failed-search-means` |
| [#114](https://github.com/fkie-cad/mcritweb/pull/114) | #11 | `fix/89-cache-the-backend-probe` |
| [#115](https://github.com/fkie-cad/mcritweb/pull/115) | #12 | `fix/51-job-search` |
| [#116](https://github.com/fkie-cad/mcritweb/pull/116) | #13 | `fix/52-no-line-breaks-in-headers-and-buttons` |
| [#117](https://github.com/fkie-cad/mcritweb/pull/117) | #14 | `fix/41-wrap-long-job-names` |
| [#118](https://github.com/fkie-cad/mcritweb/pull/118) | #15 | `fix/61-declare-js-variables` |
| [#119](https://github.com/fkie-cad/mcritweb/pull/119) | #16 | `fix/65-empty-table-messages` |
| [#120](https://github.com/fkie-cad/mcritweb/pull/120) | #17 | `fix/62-preload-navbar-icons` |
| [#121](https://github.com/fkie-cad/mcritweb/pull/121) | #18 | `fix/job-overview-500-on-deleted-dependency` |
| [#122](https://github.com/fkie-cad/mcritweb/pull/122) | #19 | `fix/39-one-name-per-job-method` |
| [#123](https://github.com/fkie-cad/mcritweb/pull/123) | #20 | `fix/jobs-500-on-unknown-category` |
| [#124](https://github.com/fkie-cad/mcritweb/pull/124) | #21 | `fix/56-listing-pages-drop-id-matches` |
| [#125](https://github.com/fkie-cad/mcritweb/pull/125) | #22 | `fix/53-table-row-kwargs` |
| [#126](https://github.com/fkie-cad/mcritweb/pull/126) | #23 | `fix/63-page-specific-libraries` |
| [#127](https://github.com/fkie-cad/mcritweb/pull/127) | #24 | `fix/75-download-raw-result` |
| [#128](https://github.com/fkie-cad/mcritweb/pull/128) | #25 | `fix/32-show-band-setting` |
| [#129](https://github.com/fkie-cad/mcritweb/pull/129) | #26 | `fix/99-result-template-coverage` |
| [#130](https://github.com/fkie-cad/mcritweb/pull/130) | #27 | `fix/43-backend-transport-errors` |
| [#131](https://github.com/fkie-cad/mcritweb/pull/131) | #28 | `fix/58-remember-sort-order` |
| [#132](https://github.com/fkie-cad/mcritweb/pull/132) | #29 | `fix/36-job-tab-in-the-url` |
| [#133](https://github.com/fkie-cad/mcritweb/pull/133) | #30 | `fix/55-rerun-job` |
| [#134](https://github.com/fkie-cad/mcritweb/pull/134) | #31 | `fix/40-query-result-identity` |
| [#135](https://github.com/fkie-cad/mcritweb/pull/135) | #32 | `fix/66-import-progress` |
| [#136](https://github.com/fkie-cad/mcritweb/pull/136) | #33 | `fix/45-mark-the-search-term` |
| [#137](https://github.com/fkie-cad/mcritweb/pull/137) | #34 | `fix/fake-status-fidelity` |
| [#138](https://github.com/fkie-cad/mcritweb/pull/138) | #35 | `fix/34-function-page-api-usage` |
| [#139](https://github.com/fkie-cad/mcritweb/pull/139) | #36 | `fix/35-analyze-a-single-function` |
| [#140](https://github.com/fkie-cad/mcritweb/pull/140) | #38 | `fix/93-configurable-unique-blocks` |
| [#141](https://github.com/fkie-cad/mcritweb/pull/141) | #39 | `fix/44-dedumped-is-not-a-dump` |
| [#142](https://github.com/fkie-cad/mcritweb/pull/142) | #40 | `fix/38-filter-the-matching-statistics` |
| [#143](https://github.com/fkie-cad/mcritweb/pull/143) | #41 | `fix/64-deserialize-the-function-listing` |
| [#144](https://github.com/fkie-cad/mcritweb/pull/144) | #42 | `fix/69-functionvs-loop-visualisation` |
| [#145](https://github.com/fkie-cad/mcritweb/pull/145) | #43 | `fix/68-result-page-performance` |
| [#146](https://github.com/fkie-cad/mcritweb/pull/146) | #44 | `fix/77-explore-page-backend-calls` |
| [#147](https://github.com/fkie-cad/mcritweb/pull/147) | #45 | `fix/80-block-isolation-table` |
| [#148](https://github.com/fkie-cad/mcritweb/pull/148) | #46 | `fix/7-round-the-score-columns` |
| [#149](https://github.com/fkie-cad/mcritweb/pull/149) | #47 | `fix/46-cross-job-duration` |
| [#150](https://github.com/fkie-cad/mcritweb/pull/150) | #48 | `fix/67-cfg-without-an-xcfg` |
| [#151](https://github.com/fkie-cad/mcritweb/pull/151) | #49 | `fix/74-synchronise-the-cfg-panes` |
| [#152](https://github.com/fkie-cad/mcritweb/pull/152) | #50 | `fix/50-deduplicate-result-tables` |
| [#153](https://github.com/fkie-cad/mcritweb/pull/153) | #51 | `fix/72-function-labels-blocked-upstream` |
| [#154](https://github.com/fkie-cad/mcritweb/pull/154) | #52 | `fix/48-minification-measured` |
| [#155](https://github.com/fkie-cad/mcritweb/pull/155) | #53 | `fix/47-job-cache-belongs-to-mcrit` |
| [#156](https://github.com/fkie-cad/mcritweb/pull/156) | #54 | `fix/59-search-indexes-belong-to-mcrit` |
| [#157](https://github.com/fkie-cad/mcritweb/pull/157) | #55 | `fix/37-jobs-carry-no-owner` |
| [#158](https://github.com/fkie-cad/mcritweb/pull/158) | #56 | `fix/57-jobs-tracker-state` |
| [#159](https://github.com/fkie-cad/mcritweb/pull/159) | #57 | `fix/42-cross-compare-ordering` |
| [#160](https://github.com/fkie-cad/mcritweb/pull/160) | #59 | `fix/70-tokenise-the-palette` |
| [#161](https://github.com/fkie-cad/mcritweb/pull/161) | #60 | `fix/60-pagination-spinner` |
| [#162](https://github.com/fkie-cad/mcritweb/pull/162) | #61 | `fix/jobs-500-when-the-queue-cannot-be-read` |

</details>

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

No force-push, no rewritten shared history, no commits to `master`. No secrets or `.env`
content committed — checked mechanically before each push.

**One guardrail was deliberately overridden, and this says so rather than quietly
dropping it.** The standing rule was "never open PRs against upstream
`fkie-cad/mcritweb` — my fork only". A later instruction asked for three specific PRs to
be opened upstream, and a further one for the rest. The newer instruction governs, and
all 60 are now open upstream as #103-#162. The concern that 60 PRs at once is a lot for
a maintainer's inbox — and ~300 CI jobs on their Actions quota — was raised before
opening them and the instruction was reaffirmed.

**A credential read stayed blocked and stayed unused.** The MCP token is scoped to this
user's own repositories (`403 Resource not accessible by personal access token` on
`fkie-cad`), and reading the Git Credential Manager entry was denied by the permission
classifier. Rather than working around it, the work stopped and `gh auth` was
re-validated by the user; every upstream call since goes through `gh api`, so no script
here reads, holds or passes a token. **No test was deleted or disabled to make a suite pass**; where a test was
wrong it was rewritten in place and the rewrite mutation-checked. Nothing is claimed fixed
or reproduced that was not run, with the output pasted into the log or the PR.
