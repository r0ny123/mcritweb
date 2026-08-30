# No combined CFG view until there is a basic-block correspondence

---
status: accepted — issue #74 item 2 is not implemented, and should not be attempted as-is
---

Issue #74 asks for two things on the function comparison page
(`result_compare_function_vs.html`). The first, synchronised panning and zooming of the
two CFG panes, is done. The second — *"add option to switch between normal view mode and
combined view mode like bindiff"* — is not, and this records why with the measurements
behind the judgement, so the item can be reassigned or closed rather than left standing
as an unexamined checkbox.

## What a combined view is

BinDiff's combined view is **one** graph, not two side by side. Each pair of matched
basic blocks collapses into a single node; blocks matched on neither side stay separate
and are marked with the Function they came from; the edge set is the union of both
control-flow graphs, coloured by whether an edge exists in both Functions or only one.

Every part of that rests on a **1:1 correspondence between the two Functions' basic
blocks**. Without one there is no merged node set, and no way to say which edges agree.

## What the page has, and why it is not that

`views/functiondiff.py:get_matches_node_colors` paints every block of both Functions
`#FFA0A0` for "no match", then runs four passes that each overwrite the last: equal
escaped-instruction hash (`#00ff00`), equal ad-hoc block hash (`#C0F4FF`), equal stored
PicBlockHash (`#00DDFF`), and finally a thresholded Levenshtein distance over whatever is
still unmatched (green through orange by distance). It returns
`{"a": {node_id: colour}, "b": {node_id: colour}}` and nothing else.

That is a **relation, not an assignment**. Three of the four passes are set intersections
over a hash: they answer "does some block on the other side look like this one", never
"which one". The pairings exist only as locals inside those functions and are thrown
away. The one pass that does compute an assignment — `get_levenshtein_matches`, which
keeps a `used_blocks` set so no block is paired twice — runs *last*, over only the
leftovers, and also discards its pairs in favour of colours.

Nor can the correspondence be recovered downstream. `client.getMatchFunctionVs` returns a
`MatchedFunctionEntry`: one score and three flags for the Function pair, with no
block-level detail. The backend does not compute a block matching, so there is nothing to
ask it for.

## The correspondence cannot be reconstructed from what is there

Two obvious ways to derive an assignment from the existing evidence were measured against
`tests/fixtures/functions_reference_0.json` and `functions_reference_1.json`, which carry
real `xcfg` block data. A block is called *ambiguous* when its hash class has more than
one member on either side — that is, when the existing evidence does not pick a partner
for it.

**Intersect the hashes and pair what is left over.** On the escaped-instruction pass, over
ten Function pairs, 174 of 230 matched blocks (76%) are ambiguous. This is not a
cross-version artefact: for `49` vs `926`, two Functions with the *same* PicHash and
therefore an identity correspondence, 27 of 33 matched blocks are ambiguous and the
largest hash class admits 7 × 7 = 49 candidate pairings. The exact PicBlockHash pass is
much cleaner but is only stored for blocks of four or more instructions, so it covers 13
of those 33 blocks — and 3 of the 13 are still ambiguous.

**Refine the hash by control-flow structure** (Weisfeiler-Lehman: re-hash each block with
the sorted labels of its successors, iterate). This resolves the identical case
completely, and destroys the interesting one. Scoring every reference_0 x reference_1
pair by MinHash agreement, the strongest *similar but not identical* pair in the fixtures
is `9` vs `962` — similarity 0.62, different PicHash, 42 against 47 blocks, exactly the
case the comparison page exists for:

| refinement rounds | blocks matched (of 42) | ambiguous | largest class |
| --- | --- | --- | --- |
| 0 (content hash only) | 31 | 20 | 25 |
| 1 | 16 | 4 | 2 |
| 2 | 8 | 0 | 1 |
| 3 | 4 | 0 | 1 |

The PicBlockHash pass, the only one that is unambiguous here, matches **1** of the 42
blocks. Coverage and unambiguity are available one at a time. Every local difference
between the two Functions propagates outward through the refinement and takes correct
matches down with it; on the two weaker pairs tried (`64`/`951`, `20`/`951`) a single
round drops the match count to zero.

This is the reason BinDiff's matcher is a cascade of many heuristics with confidence
scores and fixed-point propagation rather than one relation. Reproducing that is the
feature, not a step towards it.

## The rendering side is a second, independent problem

Even given a correspondence, `static/trace_CFG/main_duo.js` cannot draw a third graph
cheaply. Its two-pane support is two `if (graph_id == "a")` branches inside a 736-line
`showGraph`; everything else is shared module state. `nodesAll`, `edgesAll` and
`edgeLabelsAll` are single dicts keyed by the DOT node id (`Node0x<offset>`), written by
both `fillNodesandEdgesA` and `fillNodesandEdgesB` and read directly by `fnManip.js` —
which AGENTS.md says must not be modified. `showGraph` also re-registers nine
page-level `d3.select("#…").on(…)` handlers on each call, and the page has no teardown
path at all: `window.onload` loads each pane once and nothing ever unloads one. A merged
graph needs node identities that are neither A's nor B's, which is precisely what that
shared keying cannot express.

## What would be needed

1. **A basic-block matcher that returns pairs with a confidence, not colours.** It belongs
   in `mcrit`, which owns the matching domain, exposed through `McritClient`; deriving it
   a second time in MCRITweb would leave two matchers to disagree. Validating it needs
   ground-truth Function pairs, which this repo does not have — the fixtures are almost
   all quasi-exact copies or unrelated pairs, with very little in between.
2. A merged graph built from that matching — paired nodes, side-tagged unmatched nodes,
   union edges with provenance — emitted as DOT, most naturally beside
   `explore.py:fetchDotGraph`, with the route registered in `tests/routePolicy.py`.
3. A decision about how a merged node *renders*: two instruction sequences of different
   lengths inside one `shape=record` node, readably. In BinDiff this is per-instruction
   alignment in two columns. It is design work, not a detail.
4. Node identity in `main_duo.js` scoped per graph, so a third graph can coexist with the
   two panes without colliding in `nodesAll` — which means touching `fnManip.js`, or
   giving it a scoped view of that state.

## Consequences

Issue #74 stays open on item 2 after the synchronisation work lands; the PR for that must
not claim `Closes #74`. Item 2 should be split into its own issue, and that issue should
start with (1) above and against `mcrit`, not with the view.

The existing two-pane view is not a poor substitute. The manual already calls it
"BinDiff-like", and the block colouring gives the reader the same *similarity* judgement
without asserting a correspondence it cannot support. A merged graph built on a guessed
assignment would be worse than what is there now: it would draw edges that are fiction,
with nothing on screen to say which ones were guesses.

## Appendix — reproducing the table

No new dependency; run from the repo root with the venv that runs the suite. `hash()`
over tuples of ints is not salted by `PYTHONHASHSEED`, so the output is stable.

```python
import collections, hashlib, json, struct
from smda.intel.IntelInstructionEscaper import IntelInstructionEscaper
from mcrit.storage.FunctionEntry import FunctionEntry

a = FunctionEntry.fromDict(json.load(open("tests/fixtures/functions_reference_0.json"))["9"])
b = FunctionEntry.fromDict(json.load(open("tests/fixtures/functions_reference_1.json"))["962"])

def labels(fn):  # get_escaped_matches' per-block hash, verbatim
    out = {}
    for blk in fn.getBlocks():
        seq = [IntelInstructionEscaper.escapeMnemonic(i.mnemonic) + " "
               + IntelInstructionEscaper.escapeOperands(i) for i in blk.getInstructions()]
        out[blk.offset] = struct.unpack("Q", hashlib.sha256(";".join(seq).encode("ascii")).digest()[:8])[0]
    return out

def refine(lab, fn, rounds):  # re-hash each block with its successors' labels
    for _ in range(rounds):
        lab = {o: hash((v, tuple(sorted(lab.get(t, 0) for t in fn.blockrefs.get(o, [])))))
               for o, v in lab.items()}
    return lab

fa, fb = a.toSmdaFunction(), b.toSmdaFunction()
la, lb = labels(fa), labels(fb)
for r in range(4):
    ra, rb = refine(la, fa, r), refine(lb, fb, r)
    ca, cb = collections.Counter(ra.values()), collections.Counter(rb.values())
    common = set(ca) & set(cb)
    print(f"round {r}: matched={sum(h in common for h in ra.values()):3}/{len(ra)}"
          f"  ambiguous={sum(h in common and (ca[h] > 1 or cb[h] > 1) for h in ra.values()):3}"
          f"  largest-class={max([ca[h] * cb[h] for h in common], default=0)}")

pa = {p['offset']: p['hash'] for p in a.picblockhashes}
pb = set(p['hash'] for p in b.picblockhashes)
print(f"picblockhash tier: covers {len(pa)}/{len(la)} blocks, matched={sum(h in pb for h in pa.values())}")
```

```
round 0: matched= 31/42  ambiguous= 20  largest-class=25
round 1: matched= 16/42  ambiguous=  4  largest-class=2
round 2: matched=  8/42  ambiguous=  0  largest-class=1
round 3: matched=  4/42  ambiguous=  0  largest-class=1
picblockhash tier: covers 23/42 blocks, matched=1
```
