#!/usr/bin/python
"""The "Matching Method Statistics" table, over the matches a page is showing.

A match report carries one job-wide aggregation and `applyFilterValues()` never
revises it, so a result page narrowed to one family or sample used to state the whole
job's numbers - issue #38. `matching_statistics()` recomputes four of the five fields
over the filtered matches instead.

The warrant for recomputing an aggregation in the front end at all is that it
reproduces the backend's own numbers *exactly* when nothing is filtered, for every
report shape the backend produces. That is what `test_agrees_with_the_backend`
asserts, and it is the test to keep: if it ever fails, this presentation helper has
started disagreeing with the matching, which is not this repository's to change.
"""

import json
import pathlib
import re
import unittest

import pytest
from fixtureData import job_id_of
from mcrit.storage.MatchingResult import MatchingResult

from mcritweb.views.matching_statistics import matching_statistics

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
# every captured report that carries a match_aggregation, i.e. every report these
# templates render. cross_compare and unique_blocks have no aggregation at all.
REPORTS = ["matches_for_sample", "matches_for_sample_vs", "matches_for_query"]
# num_self_matches is deliberately absent: MatcherInterface._summarizeMatches drops
# self-matches from the report's function list, so nothing here can recompute it.
RECOMPUTED_FIELDS = [
    "num_own_functions_matched",
    "num_foreign_functions_matched",
    "num_own_functions_matched_as_library",
    "bytes_matched",
]


def load_report(report):
    with open(FIXTURES / f"{report}.result.json") as report_file:
        return MatchingResult.fromDict(json.load(report_file))


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


@pytest.mark.parametrize("report", REPORTS)
def test_agrees_with_the_backend(report):
    """Unfiltered, the recomputation must equal what the backend put in the report."""
    matching_result = load_report(report)
    statistics = matching_statistics(matching_result)

    for method in ("minhash", "pichash"):
        for field in RECOMPUTED_FIELDS:
            assert statistics[method][field] == matching_result.match_aggregation[method][field], f"{report}/{method}/{field}"


@pytest.mark.parametrize("report", REPORTS)
def test_self_matches_are_carried_through_unchanged(report):
    matching_result = load_report(report)
    statistics = matching_statistics(matching_result)

    assert not statistics["is_filtered"]
    for method in ("minhash", "pichash"):
        assert statistics[method]["num_self_matches"] == matching_result.match_aggregation[method]["num_self_matches"]


def test_filtering_to_a_family_narrows_the_statistics():
    """The defect itself: famid=3 is a four-function sliver of a 756-function report."""
    matching_result = load_report("matches_for_sample")
    matching_result.filterToFamilyId(3)
    statistics = matching_statistics(matching_result)

    assert statistics["is_filtered"]
    assert statistics["minhash"]["num_own_functions_matched"] == 4
    assert statistics["minhash"]["num_foreign_functions_matched"] == 7
    assert statistics["minhash"]["bytes_matched"] == 249
    # unchanged, because it cannot be recomputed - the table says so
    assert statistics["minhash"]["num_self_matches"] == matching_result.match_aggregation["minhash"]["num_self_matches"]


def test_filtering_to_a_library_family_narrows_the_library_count():
    matching_result = load_report("matches_for_sample")
    matching_result.filterToFamilyId(4)
    statistics = matching_statistics(matching_result)

    assert statistics["minhash"]["num_own_functions_matched_as_library"] == 25
    # nothing in the MSVC family matched by pichash, so that column is empty rather
    # than absent
    assert statistics["pichash"]["num_own_functions_matched"] == 0
    assert statistics["pichash"]["bytes_matched"] == 0


def test_a_filter_that_keeps_nothing_gives_zeros():
    matching_result = load_report("matches_for_sample")
    matching_result.filterToFamilyId(0x7FFFFFFF)
    statistics = matching_statistics(matching_result)

    assert statistics["is_filtered"]
    for method in ("minhash", "pichash"):
        for field in RECOMPUTED_FIELDS:
            assert statistics[method][field] == 0


def test_a_score_filter_narrows_the_statistics_too():
    """Not only famid/samid: the score filters left the table equally wrong."""
    matching_result = load_report("matches_for_sample")
    matching_result.setFilterValues({"filter_function_min_score": 100})
    matching_result.applyFilterValues()
    statistics = matching_statistics(matching_result)

    assert statistics["is_filtered"]
    assert statistics["minhash"]["num_own_functions_matched"] < matching_result.match_aggregation["minhash"]["num_own_functions_matched"]


def statistics_table_of(page):
    """The rendered statistics table as {field: (minhash, pichash)}."""
    table = re.search(r"Matching Method Statistics.*?</table>", page, re.S)
    assert table is not None, "the page has no statistics table"
    rows = re.findall(
        r"<td valign=\"middle\">(.*?): </td>\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>([^<]*)</td>",
        table.group(0),
        re.S,
    )
    # the field label is wrapped in a tooltip span on the row that cannot be filtered
    return {re.sub(r"<[^>]*>", "", field).strip(): (minhash.strip(), pichash.strip()) for field, minhash, pichash in rows}


def test_an_unfiltered_page_still_shows_the_backends_numbers(client, as_role):
    as_role("visitor")
    page = client.get(f"/data/result/{job_id_of('matches_for_sample')}")
    assert page.status_code == 200

    table = statistics_table_of(page.data.decode())
    assert table["num_own_functions_matched"] == ("756", "587")
    assert table["bytes_matched"] == ("151654.0", "87582.0")
    assert table["num_self_matches"] == ("183", "50")


def test_a_family_filtered_page_shows_that_familys_numbers(client, as_role):
    as_role("visitor")
    page = client.get(f"/data/result/{job_id_of('matches_for_sample')}?famid=3")
    assert page.status_code == 200

    table = statistics_table_of(page.data.decode())
    assert table["num_own_functions_matched"] == ("4", "1")
    assert table["num_foreign_functions_matched"] == ("7", "1")
    assert table["bytes_matched"] == ("249.0", "52.0")
    # the one field that cannot follow says so instead of pretending
    assert "num_self_matches (whole job)" in table
    assert table["num_self_matches (whole job)"] == ("183", "50")


if __name__ == "__main__":
    unittest.main()
