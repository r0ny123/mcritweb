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
import types
import unittest

import pytest
from fixtureData import job_id_of
from mcrit.storage.MatchingResult import MatchingResult

from mcritweb.views.data import count_aggregated_function_matches, order_samples

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


#: The filter values result_matches_for_sample_or_query starts from when the user has
#: set none of their own - see UserFilters.toDict().
NO_FILTERS = {
    "filter_direct_min_score": None,
    "filter_direct_nonlib_min_score": None,
    "filter_frequency_min_score": None,
    "filter_frequency_nonlib_min_score": None,
    "filter_unique_only": None,
    "filter_exclude_own_family": None,
    "filter_family_name": None,
    "filter_function_min_score": None,
    "filter_function_max_score": None,
    "filter_function_offset": None,
    "filter_max_num_families": None,
    "filter_min_num_samples": None,
    "filter_max_num_samples": None,
    "filter_exclude_library": None,
    "filter_exclude_pic": None,
    "filter_func_unique": None,
}


@pytest.mark.parametrize("report", ["matches_for_sample", "matches_for_sample_vs", "matches_for_query"])
@pytest.mark.parametrize(
    "narrow",
    [
        lambda result: None,
        lambda result: result.filterToFamilyId(1),
        lambda result: result.filterToSampleId(1),
        lambda result: result.filterToFunctionId(sorted(result.function_id_to_family_ids_matched)[0]),
        lambda result: result.filterToFunctionScore(min_score=99),
        lambda result: result.excludeLibraryMatches(),
    ],
)
def test_the_pagination_count_equals_the_aggregation_it_replaced(app, corpus_mcrit, report, narrow):
    """The function pagination used to size itself with
    len(getAggregatedFunctionMatches()), which aggregates every match in the report -
    and threw the aggregation away, leaving the template to build it again for the
    page slice. It groups by function_id and drops no group, so the row count is the
    number of distinct function_ids. That is what count_aggregated_function_matches
    returns; this is the claim, checked against the real reports. See issue #68.
    """
    matching_result = MatchingResult.fromDict(corpus_mcrit.getResultForJob(job_id_of(report)))
    matching_result.setFilterValues(dict(NO_FILTERS))
    with app.test_request_context("/"):
        narrow(matching_result)

        assert count_aggregated_function_matches(matching_result) == len(matching_result.getAggregatedFunctionMatches())


def test_the_pagination_count_of_an_empty_report_is_zero(app, corpus_mcrit):
    matching_result = MatchingResult.fromDict(corpus_mcrit.getResultForJob(job_id_of("matches_for_sample")))
    matching_result.filtered_function_matches = []

    assert count_aggregated_function_matches(matching_result) == 0


def test_the_function_table_shows_as_many_rows_as_the_pagination_promises(client, as_role, corpus_mcrit):
    """End to end: the count the pagination is built from has to be the number of rows
    the table actually produces.

    Asserted by walking every page of the table and counting the rendered rows, rather
    than by re-deriving the number - a count that agrees with a re-derivation of itself
    would agree with it whether or not the table means the same thing.
    """
    as_role("visitor")
    job_id = job_id_of("matches_for_sample")
    expected = len({match.function_id for match in MatchingResult.fromDict(corpus_mcrit.getResultForJob(job_id)).function_matches})

    rendered = set()
    for page in range(1, 20):
        response = client.get(f"/data/result/{job_id}?funp={page}&funl=100")
        assert response.status_code == 200
        assert b"are corrupted" not in response.data
        # the per-row filter anchor, which only the aggregated function table draws -
        # counting the id links instead would also count the family and library tables
        # that share the page
        rows = set(re.findall(rb"funid=(\d+)&amp;samp=1&amp;funp=1#function-matches", response.data))
        if not rows:
            break
        rendered |= rows

    assert len(rendered) == expected, f"the table produced {len(rendered)} rows for a count of {expected}"


def test_a_job_id_nobody_knows_is_reported_not_crashed(client, as_role):
    as_role("visitor")
    response = client.get("/data/result/ffffffffffffffffffffffff")
    assert response.status_code == 200
    assert b"was not found in the system" in response.data


def test_job_page_renders_for_a_finished_job(client, as_role):
    as_role("visitor")
    response = client.get(f"/data/jobs/{job_id_of('matches_for_sample')}")
    assert response.status_code == 200


# --- the cross-compare page orders its samples in one pass -------------------------

class WalkCountingList(list):
    """A list that records how often something walked it end to end."""

    def __init__(self, *args):
        super().__init__(*args)
        self.walks = 0

    def __iter__(self):
        self.walks += 1
        return super().__iter__()


def test_ordering_samples_walks_the_sample_list_once():
    """One pass to index the samples, then a lookup per position.

    Scanning the list for each position instead - which is what this replaced - walks
    it once per sample, and the page repeats the whole ordering for every matching
    method. That is the O(n^2) issue #68 asks about; timing it would be flaky, so
    count the passes.
    """
    samples = WalkCountingList(types.SimpleNamespace(sample_id=sample_id) for sample_id in range(50))

    ordered = order_samples(samples, [str(sample_id) for sample_id in reversed(range(50))])

    assert [sample.sample_id for sample in ordered] == list(reversed(range(50)))
    assert samples.walks == 1, f"the sample list was walked {samples.walks} times"


def test_ordering_samples_reports_an_id_that_is_not_there():
    samples = [types.SimpleNamespace(sample_id=sample_id) for sample_id in range(3)]

    assert order_samples(samples, ["2", "9"]) is None


def test_cross_compare_honours_a_custom_order(client, as_role):
    """The behaviour the one-pass ordering has to keep: `?custom=` reorders the rows."""
    as_role("visitor")
    job_id = job_id_of("cross_compare")
    default = client.get(f"/data/result/{job_id}")
    reordered = client.get(f"/data/result/{job_id}?custom=1,0,2,4,6")

    assert default.status_code == 200
    assert reordered.status_code == 200
    assert b"are corrupted" not in reordered.data
    assert reordered.data != default.data


def test_cross_compare_rejects_a_custom_order_naming_an_unknown_sample(client, as_role):
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('cross_compare')}?custom=1,0,9999")

    assert response.status_code == 200
    assert b"are corrupted" in response.data


if __name__ == "__main__":
    unittest.main()
