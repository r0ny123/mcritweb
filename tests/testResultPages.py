#!/usr/bin/python
"""Renders every result type against real reports from tests/fixtures/.

Until now nothing here rendered a result page: the strict fake answers with empty
shapes, which proves a route is reachable and nothing about whether the template can
survive the data. These tests run the real dispatch in `data.result()` over captured
reports, so a template that dereferences a field the backend stopped sending, or a
renderer that miscounts a filtered report, fails here rather than in a browser.

The reports come from a live instance - see tests/fixtures/regenerate.py.
"""

import logging
import re
import unittest
from html.parser import HTMLParser

import pytest
from fixtureData import job_id_of

from mcritweb.db import UserColumnSettings

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


class _MatchTableAudit(HTMLParser):
    """Measures every table on a rendered page: its cells, and how wide it is.

    The result pages build their match tables out of the macros in
    `templates/table/match_row.html`, and Jinja renders a macro called with the wrong
    number of arguments as nothing at all rather than raising. A table that lost its
    cells that way still returns 200 and still says everything the page's headings say,
    so the tests below check the tables themselves.

    `columns` weights the header cells by `colspan`, because `famlib_header` covers the
    two direct-score columns with one `Direct` header and the two frequency ones with
    one `Frequency`. That makes it the number of *body* cells a row owes, which is what
    the width check below compares against.

    `cells` is every body cell of the table in document order, which - the width check
    holding - is `columns` cells per row. That is what `column_of` slices to read one
    column down the rows, and it is why the cells are collected per table rather than
    per row: the library table on `result_compare_all.html` puts its cells outside the
    `<tr>` (see below), so nothing here can group them by row.

    Those two spans assume both halves of each pair are active: a stored column setting
    that keeps `direct_score` and drops `direct_nonlib_score` leaves a `colspan="2"`
    header over one cell, and the width check would fail. That is a real misalignment in
    the template rather than a false alarm here, but it predates the shared macros - so
    if a test ever exercises pruned settings and lands on it, fix the header, do not
    loosen this.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._open = []
        self._header_text = None
        self._cell_text = None
        self.tables = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table":
            self._open.append({"match_rows": 0, "th": 0, "td": 0, "columns": 0, "headers": [], "spans": [], "cells": []})
        elif self._open:
            if tag == "tr" and "background-color" in (attributes.get("style") or ""):
                # every match row carries its score colour; the surrounding widget
                # tables (input samples, method statistics, pagination) do not
                self._open[-1]["match_rows"] += 1
            elif tag == "th":
                self._open[-1]["th"] += 1
                colspan = attributes.get("colspan") or "1"
                span = int(colspan) if colspan.isdigit() else 1
                self._open[-1]["columns"] += span
                self._open[-1]["spans"].append(span)
                self._header_text = []
            elif tag == "td":
                self._open[-1]["td"] += 1
                self._cell_text = []

    def handle_data(self, data):
        if self._header_text is not None:
            self._header_text.append(data)
        if self._cell_text is not None:
            self._cell_text.append(data)

    def handle_endtag(self, tag):
        if tag == "th":
            if self._header_text is not None and self._open:
                self._open[-1]["headers"].append("".join(self._header_text).strip())
            self._header_text = None
        elif tag == "td":
            if self._cell_text is not None and self._open:
                self._open[-1]["cells"].append("".join(self._cell_text).strip())
            self._cell_text = None
        elif tag == "table" and self._open:
            self.tables.append(self._open.pop())


def match_tables(markup):
    """Every table in `markup` that holds match rows."""
    audit = _MatchTableAudit()
    audit.feed(markup)
    audit.close()
    return [table for table in audit.tables if table["match_rows"]]


def assert_match_tables_are_rectangular(response, context):
    """Every match table on the page has header cells, body cells, and the same number
    of body cells in every row as it has header columns.

    The width check is what catches a column appearing on one side of a table and not
    the other, which is the shape an arity slip in a `match_row.html` call takes: Jinja
    renders the wrongly-called macro as nothing, so the header keeps its columns while
    the rows lose theirs, or the reverse. Counting cells alone cannot see that - a table
    that gained a whole column still has header cells and body cells.

    Cells are counted per *table* rather than per row on purpose:
    `result_compare_all.html`'s library table opens its row with `<tr ...></tr>` and so
    its cells sit outside the row element. That is pre-existing markup this assertion
    has no business failing on, which is why the width is checked as a total rather than
    row by row.
    """
    tables = match_tables(response.data.decode("utf-8", "replace"))
    assert tables, f"{context} rendered no match table at all"
    for table in tables:
        assert table["th"], f"{context} rendered a match table with no header cells"
        assert table["td"], f"{context} rendered a match table with no body cells"
        assert table["td"] == table["columns"] * table["match_rows"], (
            f"{context} rendered a match table {table['columns']} columns wide with "
            f"{table['td']} cells over {table['match_rows']} rows"
        )


#: The reports whose result page carries match tables. The other two render their own
#: templates - cross compare and unique blocks - and have none.
REPORTS_WITH_MATCH_TABLES = ("matches_for_sample", "matches_for_sample_vs", "matches_for_query")


@pytest.mark.parametrize(
    "report",
    ["matches_for_sample", "matches_for_sample_vs", "matches_for_query", "cross_compare", "unique_blocks"],
)
def test_result_page_renders(client, as_role, report):
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of(report)}")
    assert response.status_code == 200, f"{report} did not render"
    # the h1 of result_corrupted.html - the template's *name* appears nowhere in the
    # rendered page, so asserting on that passed whatever the page actually said
    assert b"are corrupted" not in response.data
    if report in REPORTS_WITH_MATCH_TABLES:
        assert_match_tables_are_rectangular(response, report)


@pytest.mark.parametrize("report", ["matches_for_sample", "matches_for_sample_vs", "matches_for_query"])
def test_linkhunt_renders_for_every_matching_report(client, as_role, report):
    as_role("visitor")
    response = client.get(f"/data/linkhunt/{job_id_of(report)}")
    assert response.status_code == 200


#: (query parameter, the heading of the view it reaches). `result_compare_family.html`,
#: `result_compare_sample.html` and `result_compare_function.html` are reachable *only*
#: through these filters - the unfiltered dispatch above renders
#: `result_compare_all.html` and `result_compare_vs.html` and never touches the others.
FILTERED_VIEWS = [
    ("famid", b"All Matches in Family"),
    ("samid", b"Sample Match Statistics"),
    ("funid", b"Matches for Function"),
]

#: How many ids to try per report before moving on. The ids that work sit at the top of
#: the page, and every attempt re-renders a whole report.
CANDIDATES_PER_REPORT = 3


def filtered_views(client, param, heading):
    """Every (context, response) among the candidate ids that reaches the `param` view.

    The ids come off the rendered overview rather than being hardcoded: they are
    properties of the captured corpus, and `tests/fixtures/regenerate.py` would leave
    hardcoded ones pointing at nothing while the test still passed.

    Not every id reaches its view - `?samid=` and `?funid=` resolve matched function
    entries beyond the captured pool for some reports and land on
    `result_corrupted.html` instead, which `tests/fixtures/README.md` documents. So this
    walks every id each report offers and hands back the ones that arrived; it is for
    the caller to require that there was at least one.
    """
    pattern = re.compile(rb"[?&]" + param.encode() + rb"=(-?\d+)")
    for report in REPORTS_WITH_MATCH_TABLES:
        job_id = job_id_of(report)
        overview = client.get(f"/data/result/{job_id}")
        assert overview.status_code == 200, f"{report} overview did not render"
        for candidate in list(dict.fromkeys(pattern.findall(overview.data)))[:CANDIDATES_PER_REPORT]:
            value = candidate.decode()
            response = client.get(f"/data/result/{job_id}?{param}={value}")
            assert response.status_code == 200, f"{report} ?{param}={value} errored"
            if heading in response.data:
                yield f"{report} ?{param}={value}", response


@pytest.mark.parametrize("param, heading", FILTERED_VIEWS)
def test_filtered_result_view_renders(client, as_role, param, heading):
    """Every id that reaches the view is checked, not just the first one: the three
    filtered templates are otherwise each exercised through a single report, and the
    reports differ in what they carry - `matches_for_query` has no reference sample in
    the corpus, and only some reports resolve a `?samid=` at all."""
    as_role("visitor")

    rendered = []
    for context, response in filtered_views(client, param, heading):
        assert_match_tables_are_rectangular(response, context)
        rendered.append(context)

    assert rendered, (
        f"no captured report rendered the ?{param}= view. "
        "Widen the fixture pools (tests/fixtures/README.md) rather than dropping this."
    )


#: The heading each of the two pages puts above its function-to-function table. Both
#: templates anchor it, and it is the last table on either page, so the markup after it
#: is that table and nothing else.
FUNCTION_MATCHES_ANCHOR = 'id="function-matches"'


def function_match_table(response, context):
    """The one match table below the `function-matches` heading."""
    markup = response.data.decode("utf-8", "replace")
    _before, anchor, after = markup.partition(FUNCTION_MATCHES_ANCHOR)
    assert anchor, f"{context} has no function-matches heading"
    tables = match_tables(after)
    assert len(tables) == 1, f"{context} has {len(tables)} match tables below the heading, expected one"
    return tables[0]


def test_the_one_vs_one_page_leaves_out_the_column_it_cannot_answer(client, as_role):
    """`data.result()` hands `result_compare_vs.html` and `result_compare_sample.html`
    the *same* stored column list - `result_function_sample_filtered_table` - and the vs
    page renders one column fewer on purpose: a match against a single other sample says
    nothing about whether a function is unique across the corpus, so `is_unique_match` is
    left out. That is the one behaviour the shared macros carry a flag for
    (`unique_match_known`), and it is the easiest thing in this refactor to lose.

    It is easy to lose *silently*, which is why this is worth its own test. Jinja renders
    a macro called with the wrong number of arguments as nothing at all, so dropping the
    flag from one of the vs page's two call sites leaves the table a column wider on one
    side than the other, which the width check above now sees. Dropping it from *both*
    keeps the table rectangular and grows it by a real extra column: a second `Uniq`
    header, a cell on every row, and a `getFamilyIdsMatchedByFunctionId` lookup per row
    for an answer that means nothing here. Nothing else in the suite notices that one.

    Counted and compared against the sibling page rather than named, so it also fails if
    either table drifts from the stored settings for any other reason.
    """
    as_role("visitor")
    stored_columns = UserColumnSettings._default_settings["result_function_sample_filtered_table"]["active"]

    versus = client.get(f"/data/result/{job_id_of('matches_for_sample_vs')}")
    filtered = list(filtered_views(client, "samid", b"Sample Match Statistics"))

    assert versus.status_code == 200
    assert filtered, "no captured report reached the sample-filtered view to compare against"
    versus_headers = function_match_table(versus, "the 1-vs-1 page")["headers"]
    for context, response in filtered:
        filtered_headers = function_match_table(response, context)["headers"]
        assert filtered_headers == [header for header in filtered_headers if header], (
            f"{context} rendered a nameless function column"
        )
        assert len(filtered_headers) == len(stored_columns), (
            f"{context} rendered {len(filtered_headers)} of the {len(stored_columns)} stored columns"
        )
        dropped = [header for header in filtered_headers if header not in versus_headers]
        assert len(dropped) == 1, (
            f"the 1-vs-1 page should leave out exactly one of {filtered_headers}, it left out {dropped}"
        )
        assert versus_headers == [header for header in filtered_headers if header != dropped[0]], (
            f"the 1-vs-1 page rendered {versus_headers} against {filtered_headers}"
        )


def test_result_page_applies_a_score_filter(client, as_role):
    """The filter parameters drive MatchingResult.applyFilterValues, which is where a
    report gets narrowed - rendering it unfiltered proves much less."""
    as_role("visitor")
    unfiltered = client.get(f"/data/result/{job_id_of('matches_for_sample')}")
    filtered = client.get(f"/data/result/{job_id_of('matches_for_sample')}?filter_direct_min_score=99")

    assert unfiltered.status_code == 200
    assert filtered.status_code == 200
    assert filtered.data != unfiltered.data


def test_unique_blocks_page_paginates(client, as_role):
    as_role("visitor")
    first = client.get(f"/data/result/{job_id_of('unique_blocks')}")
    second = client.get(f"/data/result/{job_id_of('unique_blocks')}?blkp=2")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data != second.data


def test_a_job_id_nobody_knows_is_reported_not_crashed(client, as_role):
    as_role("visitor")
    response = client.get("/data/result/ffffffffffffffffffffffff")
    assert response.status_code == 200
    assert b"was not found in the system" in response.data


def test_job_page_renders_for_a_finished_job(client, as_role):
    as_role("visitor")
    response = client.get(f"/data/jobs/{job_id_of('matches_for_sample')}")
    assert response.status_code == 200


################################################################
# Sorting - the other half of issue #50
################################################################

def column_of(table, header):
    """The body cells under `header`, top row first.

    The audit collects body cells per table rather than per row, so a column is a
    stride through that list - offset by the widths of the headers before it, because
    `famlib_header` covers two columns with one `Direct` header.
    """
    index = table["headers"].index(header)
    start = sum(table["spans"][:index])
    return table["cells"][start::table["columns"]]


#: (report, sort parameter, the header of the column it orders). One report per kind of
#: function table: `matches_for_sample` renders the aggregated one on
#: `result_compare_all.html`, `matches_for_sample_vs` the function-to-function one on
#: `result_compare_vs.html`, and the two sort through different key tables in
#: `views/result_sorting.py`. Both hold several hundred rows at 100 to a page, which is
#: what makes the cross-page assertion below possible at all - every other match table
#: in the corpus fits on one page.
SORTABLE_FUNCTION_TABLES = [
    ("matches_for_sample", "best_score", "Best Score"),
    ("matches_for_sample_vs", "best_score", "Score"),
]


def function_table_of(client, report, context, query=""):
    response = client.get(f"/data/result/{job_id_of(report)}?{query}")
    assert response.status_code == 200, f"{report} {context} did not render"
    return function_match_table(response, f"{report} {context}")


@pytest.mark.parametrize("report, sort_by, header", SORTABLE_FUNCTION_TABLES)
def test_a_result_table_sorts_the_whole_list_and_not_only_the_page(client, as_role, report, sort_by, header):
    """The sort has to reach the rows the page is not showing.

    These tables are sliced server-side, so ordering the hundred rows that reached the
    browser - which is all a client-side sort such as the DataTables call in `jobs.html`
    can see - leaves the reader with a page that is sorted and a list that is not. The
    last row of page one being above the first row of page two is what tells the two
    apart, and it is why the sort runs in `views/result_sorting.py` over the whole
    materialised `MatchingResult` before the page is cut out of it.
    """
    as_role("visitor")
    natural = column_of(function_table_of(client, report, "unsorted"), header)
    first = [int(value) for value in column_of(function_table_of(client, report, "sorted page 1", f"funpsort={sort_by}"), header)]
    second = [int(value) for value in column_of(function_table_of(client, report, "sorted page 2", f"funpsort={sort_by}&funp=2"), header)]

    assert len(first) > 1 and len(second) > 1, f"{report} has too few rows to tell a sort from a slice"
    assert [str(value) for value in first] != natural, f"{report} ignored funpsort={sort_by}"
    assert first == sorted(first), f"{report} page 1 is not in order: {first}"
    assert second == sorted(second), f"{report} page 2 is not in order: {second}"
    assert first[-1] <= second[0], (
        f"{report} page 2 starts at {second[0]} below the {first[-1]} page 1 ended on - "
        "the sort only reached the rows that page was showing"
    )


@pytest.mark.parametrize("report, sort_by, header", SORTABLE_FUNCTION_TABLES)
def test_a_result_table_sorts_the_other_way_round(client, as_role, report, sort_by, header):
    as_role("visitor")
    ascending = [int(value) for value in column_of(function_table_of(client, report, "ascending", f"funpsort={sort_by}&funpasc=true"), header)]
    descending = [int(value) for value in column_of(function_table_of(client, report, "descending", f"funpsort={sort_by}&funpasc=false"), header)]

    assert descending == sorted(descending, reverse=True), f"{report} descending is not in order: {descending}"
    assert descending != ascending, f"{report} ignored funpasc=false"


def test_each_table_on_a_result_page_sorts_on_its_own(client, as_role):
    """Three match tables share `result_compare_all.html` and one query string, so each
    `Pagination` derives its sort parameters from its own page parameter - `fampsort`
    for the family table, `libpsort` for the library one, `funpsort` for the functions.
    Sorting one and finding the others reordered would mean they are reading each
    other's parameter."""
    as_role("visitor")
    job_id = job_id_of("matches_for_sample")
    unsorted = client.get(f"/data/result/{job_id}")
    sorted_families = client.get(f"/data/result/{job_id}?fampsort=sha256")

    assert unsorted.status_code == 200 and sorted_families.status_code == 200
    families = match_tables(sorted_families.data.decode("utf-8", "replace"))[0]
    # the cell shows the first eight characters of the hash, which orders the same way
    # the whole hash the sort key reads does
    hashes = column_of(families, "SHA256")
    assert len(hashes) > 1, "the family table has too few rows to tell a sort from a slice"
    assert hashes == sorted(hashes), f"the family table ignored fampsort=sha256: {hashes}"
    assert hashes != column_of(match_tables(unsorted.data.decode("utf-8", "replace"))[0], "SHA256")
    assert function_match_table(sorted_families, "the function table")["cells"] == function_match_table(unsorted, "the function table")["cells"], (
        "sorting the family table reordered the function table as well"
    )


def test_a_sort_link_names_its_own_table_and_returns_to_page_one(client, as_role):
    """Reading on from row 300 of an order the reader has not seen the start of is not
    useful, so `Pagination.get_sort_link` drops the page - the same thing
    `CursorPagination.get_sort_link` does for the listing pages."""
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('matches_for_sample')}?funp=3")
    markup = response.data.decode("utf-8", "replace")

    assert response.status_code == 200
    for parameter in ("fampsort=sha256", "libpsort=sha256", "funpsort=best_score"):
        assert parameter in markup, f"no header on the page links to {parameter}"
    function_sort_links = re.findall(r"window\.location\.href='([^']*funpsort=[^']*)'", markup)
    assert function_sort_links, "the function table has no sort links"
    for link in function_sort_links:
        assert "funp=1" in link, f"a sort link kept the reader on page 3: {link}"


if __name__ == "__main__":
    unittest.main()
