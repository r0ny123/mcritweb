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
from flask import template_rendered

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


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


@pytest.mark.parametrize("report", ["matches_for_sample", "matches_for_sample_vs", "matches_for_query"])
def test_linkhunt_renders_for_every_matching_report(client, as_role, report):
    as_role("visitor")
    response = client.get(f"/data/linkhunt/{job_id_of(report)}")
    assert response.status_code == 200


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


#: (report fixture, query string, the template the request has to reach). `data.result`
#: dispatches on the query parameters, so `?famid=` / `?samid=` / `?funid=` are the only
#: way to reach three of the five result templates that render a score - parametrising
#: over reports alone renders `result_compare_all.html` twice and calls it coverage.
#: The ids are the captured 1-vs-1 report's own: it matched samples 1 and 3, function 880
#: is one of its matches, and its by-id function pool is complete - the 1-vs-N report's is
#: not, so ?samid= and ?funid= land on result_corrupted.html there (fixtures/README.md).
RESULT_PAGES = [
    ("matches_for_sample", "", "result_compare_all.html"),
    ("matches_for_query", "", "result_compare_all.html"),
    ("matches_for_sample_vs", "", "result_compare_vs.html"),
    ("matches_for_sample", "?famid=1", "result_compare_family.html"),
    ("matches_for_sample_vs", "?samid=3", "result_compare_sample.html"),
    ("matches_for_sample_vs", "?funid=880", "result_compare_function.html"),
]

#: result_compare_function.html is the one of them that carries no sample-level table.
SAMPLE_SCORE_PAGES = [page for page in RESULT_PAGES if page[2] != "result_compare_function.html"]


@pytest.fixture
def renders(app):
    """(template name, context) for every template rendered during a request.

    The function-match tables render their score bare, so there is no tooltip to read
    the exact value back out of the page with - it has to come from the context the
    template was handed. Recording it also lets a test say which template it meant to
    exercise, rather than trusting a query parameter to have dispatched where it looks.

    `record` has to stay referenced for the length of the test - blinker holds its
    receivers weakly, and a receiver nobody else keeps is collected and never called.
    The generator frame this fixture suspends in is what keeps it alive.
    """
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template.name, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)


class _TableReader(HTMLParser):
    """Every <table> on a page, as a list of rows of cell text.

    Stacked rather than flat because a table macro nested in a cell would otherwise
    hand its rows to whichever table happened to be open last, and a cell would be
    read out of the wrong column without anything looking wrong.
    """

    def __init__(self):
        super().__init__()
        self.tables = []
        self._open_tables = []
        self._open_rows = []
        self._open_cells = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._open_tables.append([])
        elif tag == "tr" and self._open_tables:
            self._open_rows.append([])
        elif tag in ("td", "th") and self._open_rows:
            self._open_cells.append([])

    def handle_endtag(self, tag):
        if tag == "table" and self._open_tables:
            self.tables.append(self._open_tables.pop())
        elif tag == "tr" and self._open_rows:
            row = self._open_rows.pop()
            if self._open_tables:
                self._open_tables[-1].append(row)
        elif tag in ("td", "th") and self._open_cells:
            cell = "".join(self._open_cells.pop()).strip()
            if self._open_rows:
                self._open_rows[-1].append(cell)

    def handle_data(self, data):
        if self._open_cells:
            self._open_cells[-1].append(data)


def column_under(page, header):
    """Every cell below the column headed `header`, located the way a reader locates it.

    Rows of a different width than the header row are skipped - the sample tables put a
    `colspan` header row above their own, and it is not a row of cells.
    """
    reader = _TableReader()
    reader.feed(page)
    cells = []
    for rows in reader.tables:
        for index, row in enumerate(rows):
            if header in row:
                position, width = row.index(header), len(row)
                cells += [below[position] for below in rows[index + 1:] if len(below) == width]
                break
    return cells


def score_column(page):
    """The score column of the function-match table: headed "Best Score" where the table
    aggregates a function's matches, and "Score" where it lists them one by one."""
    for header in ("Best Score", "Score"):
        cells = column_under(page, header)
        if cells:
            return cells
    return []


def function_match_scores(template, context):
    """The scores that template's function-match table was handed, in row order."""
    matching_result, funp = context["matching_result"], context["funp"]
    if template in ("result_compare_all.html", "result_compare_family.html"):
        return [aggregate["best_score"] for aggregate in matching_result.getAggregatedFunctionMatches(funp.start_index, funp.limit)]
    return [matched_function.matched_score for matched_function in matching_result.getFunctionsSlice(funp.start_index, funp.limit)]


@pytest.mark.parametrize("report,query,template", RESULT_PAGES)
def test_function_score_column_rounds_rather_than_truncates(client, as_role, renders, report, query, template):
    """The function-match table truncated its score the same way the sample columns did.

    `MatchedFunctionEntry.matched_score` is a float and `MatchingResult` maxes it into
    `best_score`, so `%d` showed 93.75 as 93 - issue #7 again, one table lower on the
    same page, in a column that is active by default and needs no query parameter.

    These cells carry no tooltip and are marked up exactly like the byte counts beside
    them, so they are found by the header over the column and checked against the value
    the render context holds, which is the score itself rather than a rounding of it.
    """
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of(report)}{query}")
    assert response.status_code == 200
    assert renders, f"{report}{query} rendered no template at all"
    assert renders[-1][0] == template, f"{report}{query} rendered {renders[-1][0]}, not {template}"

    exact = function_match_scores(*renders[-1])
    shown = score_column(response.data.decode())
    assert exact, f"{template} rendered no function matches to check"
    assert len(shown) == len(exact), f"{template}: {len(shown)} score cells for {len(exact)} function matches"

    not_rounded = [(score, cell) for score, cell in zip(exact, shown) if int(cell) != round(score)]
    assert not not_rounded, f"{template}: score cells not rounded: {not_rounded}"


# every sample score cell renders the exact percentage into its hover text and an integer
# into the cell itself:  ... Percent: 85.88%">  85</span>
SCORE_CELL = re.compile(r"Percent:\s*(\d+\.\d+)%\">\s*(-?\d+)\s*</span>")


def score_cells(page):
    """(exact percent, integer shown) for every score cell on a rendered page."""
    return [
        (float(percent), int(shown))
        for percent, shown in SCORE_CELL.findall(page)
    ]


@pytest.mark.parametrize("report,query,template", SAMPLE_SCORE_PAGES)
def test_score_columns_round_rather_than_truncate(client, as_role, renders, report, query, template):
    """`%d` truncates toward zero, so a sample scoring 85.88 showed as 85 - a whole
    point below what the tooltip on the same cell says, and 0.76 showed as 0 next to
    a neighbour at 1.04 that had scored barely more (issue #7).

    The assertion below is a half-unit tolerance rather than an equality because the
    tooltip is the score rounded to two decimals rather than the score itself; see the
    comment on TOOLTIP_PRECISION for why that makes an equality wrong here.
    """
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of(report)}{query}")
    assert response.status_code == 200
    assert renders, f"{report}{query} rendered no template at all"
    assert renders[-1][0] == template, f"{report}{query} rendered {renders[-1][0]}, not {template}"

    cells = score_cells(response.data.decode())
    assert cells, f"{report}{query} rendered no score cells to check"
    # The tooltip is the score to two decimals, so it is not the source value: a score
    # of 2.501 renders as tooltip "2.50" and cell "3", and asserting shown == round(2.50)
    # would fail on a correct page. What the tooltip does pin is an interval - the score
    # is within 0.005 of it - so the cell must be within half a unit of that interval.
    # Truncation is caught all the same: it is off by the whole fractional part, and
    # these reports carry plenty above 0.505 (85.88, 82.70, 42.81, 60.99).
    TOOLTIP_PRECISION = 0.005
    not_rounded = [(exact, shown) for exact, shown in cells if abs(shown - exact) > 0.5 + TOOLTIP_PRECISION]
    assert not not_rounded, f"{report}{query}: score cells not rounded: {not_rounded}"


# the same hover text states a fraction above its percentage, and the percentage has to
# be that fraction:  ... Bytes: 130682.88 / 152337.00 &#10;Percent: 85.79%
SCORE_TOOLTIP = re.compile(r"Bytes:\s*(-?\d+\.\d+)\s*/\s*(\d+\.\d+)\s*&#10;Percent:\s*(-?\d+\.\d+)%")

#: Both numbers in the fraction and the percentage itself are rendered to two decimals,
#: so the quotient can miss the stated percentage by the percentage's own rounding. The
#: numerator's rounding contributes ~4e-8 relative on these reports and is ignored.
TWO_DECIMALS = 0.005 + 1e-6


@pytest.mark.parametrize("report,query,template", SAMPLE_SCORE_PAGES)
def test_score_tooltips_divide_by_the_total_their_percentage_uses(client, as_role, renders, report, query, template):
    """The hover text used to print the sample's binweight as the divisor while
    stating a percentage taken against a different total - the matchable bytes, or
    for the `nonlib_` columns the matchable bytes minus the library-matching ones.
    On the top match of `matches_for_sample` it offered 130682.88 / 155065 = 84.28
    and then said 85.79%.

    That is what sets a reader's expectation, and issue #7 is a report of the value
    being "too far from the expected value" - so an inconsistency here is the defect,
    not a cosmetic one. See docs/adr/0009-nonlib-frequency-score.md.
    """
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of(report)}{query}")
    assert response.status_code == 200
    assert renders and renders[-1][0] == template, f"{report}{query} did not render {template}"

    page = response.data.decode()
    tooltips = SCORE_TOOLTIP.findall(page)
    assert tooltips, f"{report}{query} rendered no score tooltip to check"

    inconsistent = [
        (numerator, divisor, percent)
        for numerator, divisor, percent in (
            (float(a), float(b), float(c)) for a, b, c in tooltips
        )
        if abs(100.0 * numerator / divisor - percent) > TWO_DECIMALS
    ]
    assert not inconsistent, (
        f"{report}{query}: hover text states a fraction that is not its percentage: {inconsistent}"
    )

    # A report whose functions were all matchable and none library-matched would make
    # the check above pass against the binweight too, so pin that the divisor actually
    # moved off it. None of the three fixtures is that report.
    binweight = renders[-1][1]["matching_result"].reference_sample_entry.binweight
    assert any(float(divisor) != binweight for _, divisor, _ in tooltips), (
        f"{report}{query}: every score tooltip still divides by the sample binweight {binweight}"
    )


if __name__ == "__main__":
    unittest.main()
