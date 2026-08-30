#!/usr/bin/python
"""The single-function page, rendered against the captured corpus.

Issue #34 asks for several things on this page at once. Three of them are covered
here. Two are data that already exists in a `FunctionEntry` and which the page never
showed:

  * whether the function has a **MinHash**. A function below the backend's size
    thresholds (`MINHASH_FN_MIN_INS` / `MINHASH_FN_MIN_BLOCKS`) never gets one, and
    then it can only ever be found by PicHash. The function *tables* have shown this
    for a while - `table/function_row.html` has a `has_minhash` column - but the
    single-function page, the one place an analyst lands to ask "why did this not
    match anything", did not.
  * which **imported APIs** the function calls. smda records these in
    `xcfg["apirefs"]`, one entry per call site, so they arrive only when the entry is
    fetched `with_xcfg`.

The third is the accordion those sections now sit in, which is the only reason the
API list can be on the page without pushing the CFG off the bottom of it.

The corpus has real instances of every branch: 32 of its 609 functions have no
MinHash, 117 of the 200 that carry an xcfg call at least one API, and the remaining
409 were captured with the xcfg dropped, which is the "unknown" case.

`with_xcfg` is the whole feature: without it the backend answers an entry whose
`xcfg` is None and every function on the site reports its API calls as unknown, so
`CorpusMcritClient.getFunctionById` honours the flag rather than always handing the
graph back. The page's second request, `/explore/fetchDotGraph`, needs the same flag,
and its own test says so.

The API names are worth a paranoid test of their own. They come out of a sample that
somebody uploaded - a name is whatever the import table of a piece of malware says it
is - so `test_a_crafted_api_name_cannot_inject_markup` renders one that tries to
close the surrounding element and open a script, the same shape as the family-name
breakout of issue #85.
"""

import logging
import unittest
from collections import Counter

import pytest
from markupsafe import escape

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

#: An import name that ends the attribute it might land in, closes the cell and opens
#: a script. Autoescaping turns all of it into text; nothing here may survive as markup.
BREAKOUT_API = 'evil.dll!Load"><script>alert(1)</script>'


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


def function_with(corpus, predicate):
    """The lowest function id in the corpus whose entry satisfies `predicate`.

    Picking by property rather than hard-coding an id keeps these tests tied to what
    the case actually needs, so regenerating the fixtures cannot quietly turn a
    "has no MinHash" test into a "has one" test.
    """
    for function_id in sorted(corpus._functions):
        if predicate(corpus._functions[function_id]):
            return function_id
    raise AssertionError("no function in tests/fixtures/ satisfies this predicate")


def apirefs_of(entry):
    return (entry.xcfg or {}).get("apirefs") or {}


def most_shared_block_hash(corpus):
    """The PicBlockHash carried by the most functions in the corpus.

    Picked by property for the same reason `function_with` exists: a hard-coded hash
    would only be the interesting, several-function case until the fixtures move.
    """
    holders = Counter(
        block_hash
        for entry in corpus._functions.values()
        for block_hash in {block["hash"] for block in entry.picblockhashes}
    )
    block_hash, num_functions = holders.most_common(1)[0]
    assert num_functions > 1, "no basic block in tests/fixtures/ is shared by two functions"
    return block_hash


def function_column(corpus, function_id, heading):
    """One column of `function_column_table`: (heading, function, sample, pichash)."""
    entry = corpus._functions[function_id]
    return (heading, entry, corpus._samples[entry.sample_id], corpus.getMatchesForPicHash(entry.pichash, summary=True))


def render_function_column_table(app, *columns):
    """`table/column_table.html`'s two-column function table, rendered on its own.

    `result_compare_function_vs.html` is the page that gives this macro more than one
    column, and it cannot be reached offline: its route needs `getMatchFunctionVs`,
    a match report the captured corpus has no fixture for. The macro itself has no
    such dependency, so the multi-column shape is proven here directly.
    """
    with app.test_request_context():
        macro = app.jinja_env.get_template("table/column_table.html").module.function_column_table
        return str(macro(*columns))


def render_function_rows(app, corpus, *function_ids):
    """`table/function_row.html`'s row macro, rendered for the named functions.

    The listing page renders whichever functions its first page holds, which is a
    property of the fixtures; a test about the markup of a branch has to choose the
    function that takes it.
    """
    with app.test_request_context():
        macro = app.jinja_env.get_template("table/function_row.html").module.function_row
        return "".join(str(macro(corpus._functions[function_id])) for function_id in function_ids)


def test_function_page_renders(client, as_role, fake_mcrit):
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: bool(entry.xcfg))

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200


def test_the_page_reports_a_present_minhash(client, as_role, fake_mcrit):
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: len(entry.minhash) > 0)

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200
    assert b"MinHash present" in response.data
    assert b"MinHash missing" not in response.data


def test_the_page_reports_a_missing_minhash(client, as_role, fake_mcrit):
    """The branch that matters: no MinHash means no similarity matching for this
    function at all, which is the answer to "why is it not in my results"."""
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: len(entry.minhash) == 0)

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200
    assert b"MinHash missing" in response.data
    assert b"MinHash present" not in response.data


def test_the_page_lists_the_apis_the_function_calls(client, as_role, fake_mcrit):
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: len(apirefs_of(entry)) > 1)
    expected = set(apirefs_of(fake_mcrit._functions[function_id]).values())

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200
    for api in expected:
        # compared in its escaped form, the same way Jinja wrote it - an import name
        # holding an `&` is legal and would otherwise fail this for the wrong reason
        assert str(escape(api)).encode() in response.data, f"{api} is not on the page"


def test_repeated_calls_to_one_api_are_counted_once(client, as_role, fake_mcrit):
    """`apirefs` is keyed by call site, so a function calling one API three times has
    three entries for it. The page lists each API once, with how often it is called."""
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: len(apirefs_of(entry)) > 0)
    entry = fake_mcrit._functions[function_id]
    base_offset = max(int(offset) for offset in apirefs_of(entry))
    entry.xcfg["apirefs"] = {
        str(base_offset + 4): "kernel32.dll!Sleep",
        str(base_offset + 8): "kernel32.dll!Sleep",
        str(base_offset + 12): "kernel32.dll!Sleep",
    }

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200
    assert response.data.count(b"kernel32.dll!Sleep") == 1
    assert b"API Usage (1)" in response.data


def test_a_function_calling_no_apis_says_so(client, as_role, fake_mcrit):
    """Distinct from "we did not fetch the graph": an empty answer is a finding."""
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: bool(entry.xcfg))
    fake_mcrit._functions[function_id].xcfg["apirefs"] = {}

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200
    assert b"does not reference any imported APIs" in response.data


@pytest.mark.parametrize("break_apirefs", [
    pytest.param(lambda xcfg: xcfg.pop("apirefs"), id="missing"),
    pytest.param(lambda xcfg: xcfg.update(apirefs=["kernel32.dll!Sleep"]), id="not-a-mapping"),
])
def test_a_graph_whose_apirefs_are_the_wrong_shape_does_not_claim_zero_apis(client, as_role, fake_mcrit, break_apirefs):
    """`apirefs` is one of smda's REQUIRED_FUNCTION_FIELDS, so a stored graph that has
    none, or one that is not a mapping of call site to name, is a broken shape rather
    than a function that calls nothing. Reporting it as "calls nothing" would be a
    confident answer to a question the data cannot answer, and would hide the break -
    the page says "unknown", the same as for a graph it never fetched."""
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: bool(entry.xcfg))
    break_apirefs(fake_mcrit._functions[function_id].xcfg)

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200
    assert b"does not reference any imported APIs" not in response.data
    assert b"no control flow information" in response.data


def test_an_entry_without_a_control_flow_graph_does_not_claim_zero_apis(client, as_role, fake_mcrit):
    """A function whose disassembly was dropped has an empty `xcfg` rather than a
    missing one - `MongoDbStorage.getFunctionById` calls that out as part of the
    contract, alongside `None` for "not requested". Neither is evidence that the
    function calls no APIs, so the page must not report it as such."""
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: not entry.xcfg)

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200
    assert b"does not reference any imported APIs" not in response.data
    assert b"no control flow information" in response.data


def test_the_cfg_the_page_fetches_carries_its_graph(client, as_role, fake_mcrit):
    """The picture comes from a second request, `/explore/fetchDotGraph`, and it needs
    the same `with_xcfg` the page itself does: the dot graph *is* the disassembly, so
    an entry fetched without it has nothing to draw. `toDotGraph(with_api=True)` is
    also where the API names on the picture come from, which is why the same corpus
    entry proves both."""
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: len(apirefs_of(entry)) > 0)
    called_apis = set(apirefs_of(fake_mcrit._functions[function_id]).values())

    response = client.get(f"/explore/fetchDotGraph/{function_id}")

    assert response.status_code == 200
    assert b"digraph" in response.data
    for api in called_apis:
        assert api.encode() in response.data, f"{api} is not labelled on the graph"


def test_the_page_sections_are_collapsible(client, as_role, fake_mcrit):
    """The accordion of #34. `data-bs-parent` is deliberately absent - the sections
    are independent, so opening the API list must not close the overview."""
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: bool(entry.xcfg))

    response = client.get(f"/explore/functions/{function_id}")
    body = response.data.decode()
    # only the accordion itself - base.html's navbar has collapsibles of its own
    sections = body[body.index('id="function_sections"'):body.index("Function CFG")]

    assert response.status_code == 200
    assert 'class="accordion' in body
    assert sections.count("accordion-item") == 2
    assert "data-bs-parent" not in sections


def test_a_crafted_api_name_cannot_inject_markup(client, as_role, fake_mcrit):
    """An import name is whatever the analysed binary says it is."""
    as_role("visitor")
    function_id = function_with(fake_mcrit, lambda entry: len(apirefs_of(entry)) > 0)
    entry = fake_mcrit._functions[function_id]
    entry.xcfg["apirefs"] = {str(next(iter(entry.xcfg["apirefs"]))): BREAKOUT_API}

    response = client.get(f"/explore/functions/{function_id}")

    assert response.status_code == 200
    assert b"<script>alert(1)</script>" not in response.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in response.data


def test_the_minhash_column_of_a_function_table_is_a_closed_element(app, fake_mcrit):
    """`table/function_row.html` built its icon as `<i {% if %}...{% else %}...> {% endif %}</i>`,
    so the `>` that ends the opening tag only existed on the "no MinHash" branch. The
    present branch therefore emitted `<i class="..." </i>`, which a browser recovers
    from by inventing attributes named `<` and `i` - and which swallows whatever
    follows into the tag until the next `>`. Both branches must close their own tag.

    The rows are rendered for two functions chosen by property rather than for a page
    of the listing: which functions land on page 1 is a property of the fixtures, and
    regenerating them could leave the page with only one of the two branches on it and
    fail this for a reason that has nothing to do with the markup.
    """
    rows = render_function_rows(
        app,
        fake_mcrit,
        function_with(fake_mcrit, lambda entry: len(entry.minhash) > 0),
        function_with(fake_mcrit, lambda entry: len(entry.minhash) == 0),
    )

    assert 'title="MinHash present"></i>' in rows
    assert 'title="MinHash missing"></i>' in rows
    assert 'fa-square-check" </i>' not in rows


def test_the_cfg_block_tooltip_says_how_widely_a_block_is_shared(client, as_role, fake_mcrit):
    """Each node of the CFG on this page can be asked who else has that basic block;
    `/explore/getPicBlockMatches` is what answers, and the counts it reports are the
    ones the tooltip prints. The four keys and the ordering between them are the whole
    shape of the answer - a summary where more families than samples carry a block, or
    that reports blocks nothing holds, is not a summary of anything."""
    as_role("visitor")
    block_hash = most_shared_block_hash(fake_mcrit)
    # counted here rather than asked of the backend, so the answer is checked against
    # the corpus and not against itself
    holders = {
        function_id
        for function_id, entry in fake_mcrit._functions.items()
        if any(block["hash"] == block_hash for block in entry.picblockhashes)
    }

    response = client.get(f"/explore/getPicBlockMatches/{block_hash:x}")

    assert response.status_code == 200
    summary = response.get_json()
    assert set(summary) == {"families", "samples", "functions", "offsets"}
    assert summary["functions"] == len(holders)
    assert 1 <= summary["families"] <= summary["samples"] <= summary["functions"] <= summary["offsets"]


def test_a_function_id_nobody_knows_is_reported_not_crashed(client, as_role):
    as_role("visitor")
    response = client.get("/explore/functions/999999", follow_redirects=True)

    assert response.status_code == 200
    assert b"doesn&#39;t exist" in response.data


def test_the_minhash_row_is_rendered_once_per_compared_function(app, fake_mcrit):
    """The 1-vs-1 comparison page shares this table, and there the macro is called with
    two functions rather than one. Each column has to answer for its own function, so a
    row that read the wrong column - or that only ever ran once - would show here and
    not on the single-function page."""
    with_minhash = function_with(fake_mcrit, lambda entry: len(entry.minhash) > 0)
    without_minhash = function_with(fake_mcrit, lambda entry: len(entry.minhash) == 0)

    table = render_function_column_table(
        app,
        function_column(fake_mcrit, with_minhash, "Function Info A"),
        function_column(fake_mcrit, without_minhash, "Function Info B"),
    )

    assert table.count('title="MinHash present"></i>') == 1
    assert table.count('title="MinHash missing"></i>') == 1
    # the present column comes first, as its function was passed first
    assert table.index("MinHash present") < table.index("MinHash missing")


if __name__ == "__main__":
    unittest.main()
