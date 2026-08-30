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
import unittest

import pytest
from fixtureData import job_id_of

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


def test_unique_blocks_statistics_carries_a_sample_version(client, as_role):
    """The report names samples by id only - `statistics["by_sample_id"]` is block
    counts - so the version has to be looked up on the backend (issue #80)."""
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('unique_blocks')}")

    assert response.status_code == 200
    page = response.data.decode()
    assert "Block Statistics across Samples" in page
    statistics_table = page.split("Block Statistics across Samples")[1].split("</table>")[0]
    assert ">Version<" in statistics_table
    # the versions of the three win.citadel samples the captured report covers
    for version in ("1.3.5.1", "1.3.4.0", "0.0.1.1"):
        assert version in statistics_table, f"{version} missing from the statistics table"


def test_unique_blocks_statistics_columns_are_sortable(client, as_role):
    """Sorting happens in the page, over data that is already fully in memory. The
    cells carry the raw number so a formatted cell ("2844 (66.76%)") still sorts
    numerically."""
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('unique_blocks')}")
    page = response.data.decode()

    assert response.status_code == 200
    assert 'data-sort="number"' in page
    assert 'data-sort="text"' in page
    assert 'data-sort-value="2844"' in page


def test_unique_blocks_page_survives_a_backend_that_lost_a_sample(client, as_role, fake_mcrit):
    """A deleted sample resolves to None. The version column has nothing to show for
    it, which is not a reason to lose the whole report."""
    as_role("visitor")
    fake_mcrit.getSampleById = lambda sample_id, *args, **kwargs: None
    response = client.get(f"/data/result/{job_id_of('unique_blocks')}")

    assert response.status_code == 200
    assert b"Block Statistics across Samples" in response.data


class _StubSample:
    def __init__(self, sample_id, version):
        self.sample_id = sample_id
        self.version = version


class _StubFamily:
    def __init__(self, samples=None):
        self.samples = samples


class _StubClient:
    """Answers getSampleById from a dict and counts what it was asked for."""

    def __init__(self, samples):
        self.samples = samples
        self.requested = []

    def getSampleById(self, sample_id):
        self.requested.append(sample_id)
        return self.samples.get(sample_id)


def test_sample_versions_come_from_the_family_without_extra_requests():
    """getFamily already answers with the family's samples, and result_unique_blocks
    has that entry in hand before the statistics table is built."""
    from mcritweb.views.data import get_sample_versions

    client = _StubClient({})
    family = _StubFamily({"0": _StubSample(0, "1.0"), "1": _StubSample(1, "2.0")})

    assert get_sample_versions(client, family, [0, 1]) == {0: "1.0", 1: "2.0"}
    assert client.requested == []


def test_sample_versions_fall_back_to_a_lookup_per_sample():
    """The sample-job case has no family, and a backend answering a family without
    its samples lands here too."""
    from mcritweb.views.data import get_sample_versions

    client = _StubClient({7: _StubSample(7, "3.x")})

    assert get_sample_versions(client, None, [7]) == {7: "3.x"}
    assert client.requested == [7]


def test_sample_versions_omit_a_sample_the_backend_no_longer_has():
    from mcritweb.views.data import get_sample_versions

    client = _StubClient({})

    assert get_sample_versions(client, _StubFamily(None), [7]) == {}
    assert client.requested == [7]


if __name__ == "__main__":
    unittest.main()
