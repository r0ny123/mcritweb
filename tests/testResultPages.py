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

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


class _MatchTableAudit(HTMLParser):
    """Counts the cells of every table on a rendered page.

    The result pages build their match tables out of the macros in
    `templates/table/match_row.html`, and Jinja renders a macro called with the wrong
    number of arguments as nothing at all rather than raising. A table that lost its
    cells that way still returns 200 and still says everything the page's headings say,
    so the tests below check the tables themselves.
    """

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self._open = []
        self.tables = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table":
            self._open.append({"match_rows": 0, "th": 0, "td": 0})
        elif self._open:
            if tag == "tr" and "background-color" in (attributes.get("style") or ""):
                # every match row carries its score colour; the surrounding widget
                # tables (input samples, method statistics, pagination) do not
                self._open[-1]["match_rows"] += 1
            elif tag in ("th", "td"):
                self._open[-1][tag] += 1

    def handle_endtag(self, tag):
        if tag == "table" and self._open:
            self.tables.append(self._open.pop())


def assert_match_tables_have_cells(response, context):
    """Every match table on the page has header cells and body cells.

    Cells are counted per *table* rather than per row on purpose:
    `result_compare_all.html`'s library table opens its row with `<tr ...></tr>` and so
    its cells sit outside the row element. That is pre-existing markup this assertion
    has no business failing on.
    """
    audit = _MatchTableAudit()
    audit.feed(response.data.decode("utf-8", "replace"))
    audit.close()
    tables = [table for table in audit.tables if table["match_rows"]]
    assert tables, f"{context} rendered no match table at all"
    for table in tables:
        assert table["th"], f"{context} rendered a match table with no header cells"
        assert table["td"], f"{context} rendered a match table with no body cells"


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
        assert_match_tables_have_cells(response, report)


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


@pytest.mark.parametrize("param, heading", FILTERED_VIEWS)
def test_filtered_result_view_renders(client, as_role, param, heading):
    """The ids come off the rendered overview rather than being hardcoded: they are
    properties of the captured corpus, and `tests/fixtures/regenerate.py` would leave
    hardcoded ones pointing at nothing while the test still passed.

    Not every id reaches its view - `?samid=` and `?funid=` resolve matched function
    entries beyond the captured pool for some reports and land on
    `result_corrupted.html` instead, which `tests/fixtures/README.md` documents. So this
    walks the ids each report offers and requires that one of them renders the view.
    """
    as_role("visitor")
    pattern = re.compile(rb"[?&]" + param.encode() + rb"=(-?\d+)")
    tried = []
    for report in REPORTS_WITH_MATCH_TABLES:
        job_id = job_id_of(report)
        overview = client.get(f"/data/result/{job_id}")
        assert overview.status_code == 200, f"{report} overview did not render"
        for candidate in list(dict.fromkeys(pattern.findall(overview.data)))[:CANDIDATES_PER_REPORT]:
            value = candidate.decode()
            response = client.get(f"/data/result/{job_id}?{param}={value}")
            assert response.status_code == 200, f"{report} ?{param}={value} errored"
            if heading in response.data:
                assert_match_tables_have_cells(response, f"{report} ?{param}={value}")
                return
            tried.append(f"{report} ?{param}={value}")
    pytest.fail(
        f"no captured report rendered the ?{param}= view; tried {tried}. "
        "Widen the fixture pools (tests/fixtures/README.md) rather than dropping this."
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


if __name__ == "__main__":
    unittest.main()
