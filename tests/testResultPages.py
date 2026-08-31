#!/usr/bin/python
"""Renders every result type against real reports from tests/fixtures/.

Until now nothing here rendered a result page: the strict fake answers with empty
shapes, which proves a route is reachable and nothing about whether the template can
survive the data. These tests run the real dispatch in `data.result()` over captured
reports, so a template that dereferences a field the backend stopped sending, or a
renderer that miscounts a filtered report, fails here rather than in a browser.

The reports come from a live instance - see tests/fixtures/regenerate.py.
"""

import copy
import logging
import unittest

import pytest
from fixtureData import job_id_of
from mcrit.queue.LocalQueue import Job

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


@pytest.mark.parametrize("report", ["cross_compare", "unique_blocks"])
def test_linkhunt_reports_a_report_it_cannot_read_instead_of_500ing(client, as_role, report):
    """A job id is part of the URL, so any of them can be asked for a link hunt.

    Only the matching reports carry one. The other job types used to reach the end of
    the dispatch in `data.linkhunt` and return None, which Flask answers with a 500.
    """
    as_role("visitor")
    response = client.get(f"/data/linkhunt/{job_id_of(report)}")
    assert response.status_code == 200, f"{report} did not render"
    # the sentence in result_incompatible.html
    assert b"incompatible with the requested interpretation" in response.data


# --- jobs that store no result at all ----------------------------------------
#
# The fix above put the fallback inside `if result_json:`, so it only reached job types
# that happen to produce a report. A minhashing job or a collection change stores no
# result and is finished the moment it runs, so it fell to the old `elif job_info:` and
# rendered a progress page - for a job that ended long ago, permanently, since nothing
# about it will ever change again. Same for a failed job, a terminated one, and a
# matching job whose report came back empty.

def _job_like(method, result="r", attempts_left=3, terminated=False, finished=True):
    return {
        "_id": "aaaaaaaaaaaaaaaaaaaaaaaa",
        "number": 1,
        "payload": {"method": method, "params": '{"0": 0}', "file_params": "{}", "descriptor": None},
        "all_dependencies": [],
        "created_at": {"$date": "2026-01-01T00:00:00.000Z"},
        "started_at": {"$date": "2026-01-01T00:00:01.000Z"},
        "finished_at": {"$date": "2026-01-01T00:00:02.000Z"} if finished else None,
        "last_error": None,
        "terminated": terminated,
        "attempts_left": attempts_left,
        "progress": 1,
        "result": result,
    }


class OneJob:
    """A backend holding exactly one job, and the result it did or did not produce."""

    def __init__(self, job_data, result_json=None):
        self._job = job_data
        self._result = result_json

    def getJobData(self, job_id, *args, **kwargs):
        from mcrit.queue.LocalQueue import Job
        return Job(self._job, None) if job_id == self._job["_id"] else None

    def getResultForJob(self, job_id, *args, **kwargs):
        return self._result


@pytest.fixture
def one_job(app, client, as_role):
    def _one_job(job_data, result_json=None):
        backend = OneJob(job_data, result_json)
        app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: backend
        as_role("visitor")
        return client.get(f"/data/linkhunt/{job_data['_id']}")
    return _one_job


@pytest.mark.parametrize(
    "method",
    ["updateMinHashes", "updateMinHashesForSample", "rebuildIndex", "addBinarySample", "deleteSample"],
)
def test_a_finished_job_that_stores_no_result_is_not_called_in_progress(one_job, method):
    response = one_job(_job_like(method, result=None))

    assert response.status_code == 200
    assert b"Job in Progress" not in response.data
    assert b"incompatible" in response.data


def test_a_failed_job_says_it_failed(one_job):
    response = one_job(_job_like("getMatchesForSample", result=None, attempts_left=0))

    assert response.status_code == 200
    assert b"Job in Progress" not in response.data
    assert b"did not finish" in response.data
    assert b"ran out of attempts" in response.data


def test_a_terminated_job_says_it_was_terminated(one_job):
    response = one_job(_job_like("getMatchesForSample", result=None, terminated=True))

    assert response.status_code == 200
    assert b"Job in Progress" not in response.data
    assert b"terminated before it could finish" in response.data


def test_a_matching_job_with_an_empty_report_is_not_called_in_progress(one_job):
    """Right kind of job, nothing to hunt through - which is an answer, not a wait."""
    response = one_job(_job_like("getMatchesForSample"), result_json={})

    assert response.status_code == 200
    assert b"Job in Progress" not in response.data
    assert b"does not contain any data" in response.data


def test_a_job_that_really_is_running_still_says_so(one_job):
    """The branch has to survive: this is the one case the progress page is for."""
    response = one_job(_job_like("getMatchesForSample", result=None, finished=False))

    assert response.status_code == 200
    assert b"Job in Progress" in response.data


def test_linkhunt_for_a_job_id_nobody_knows_says_it_was_not_found(client, as_role):
    """Unknown job id and wrong report type are different answers, and were swapped:
    the unknown case rendered "incompatible with the requested interpretation"."""
    as_role("visitor")
    response = client.get("/data/linkhunt/ffffffffffffffffffffffff")
    assert response.status_code == 200
    assert b"was not found in the system" in response.data


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


def test_a_finished_job_with_an_empty_result_says_the_result_is_empty(client, as_role, corpus_mcrit, monkeypatch):
    """An empty report is a result, not a missing one.

    `data.result` opens with `if result_json:`, and {} is falsy, so a finished job
    whose report is empty skipped the whole dispatch and fell through to the page for
    an unknown job id - which told the reader their job did not exist. Issue #73.
    """
    as_role("visitor")
    monkeypatch.setattr(corpus_mcrit, "getResultForJob", lambda *args, **kwargs: {})

    response = client.get(f"/data/result/{job_id_of('matches_for_sample')}")

    assert response.status_code == 200
    # the sentence in result_empty.html
    assert b"does not contain any data" in response.data
    # ... and not the one in result_invalid.html
    assert b"was not found in the system" not in response.data


# --- the other reasons a finished job has no report to show -------------------
#
# The first pass distinguished "empty" from "unknown job id" and then merged three
# further reasons back together. Each of these was reported as something it is not.

def _with_job(corpus_mcrit, monkeypatch, **changes):
    """The corpus's 1vN job, with fields overridden, and no result to hand back."""
    job_data = copy.deepcopy(corpus_mcrit.getJobData(job_id_of("matches_for_sample"))._data)
    job_data.update(changes)
    monkeypatch.setattr(corpus_mcrit, "getJobData", lambda *args, **kwargs: Job(job_data, None))
    monkeypatch.setattr(corpus_mcrit, "getResultForJob", lambda *args, **kwargs: None)
    return job_id_of("matches_for_sample")


def test_a_failed_job_is_not_reported_as_an_unknown_one(client, as_role, corpus_mcrit, monkeypatch):
    """result_invalid.html says the job "was not found in the system". For a failed job
    that is false in both halves - it is in the system and this view is holding its Job
    object. Merging failed into unknown is the same conflation issue #73 is about."""
    as_role("visitor")
    job_id = _with_job(corpus_mcrit, monkeypatch, attempts_left=0)

    response = client.get(f"/data/result/{job_id}")

    assert response.status_code == 200
    assert b"was not found in the system" not in response.data
    assert b"ran out of attempts" in response.data


def test_a_terminated_job_is_not_reported_as_an_unknown_one(client, as_role, corpus_mcrit, monkeypatch):
    as_role("visitor")
    job_id = _with_job(corpus_mcrit, monkeypatch, terminated=True)

    response = client.get(f"/data/result/{job_id}")

    assert response.status_code == 200
    assert b"was not found in the system" not in response.data
    assert b"terminated before it could finish" in response.data


def test_a_report_that_cannot_be_fetched_is_not_reported_as_an_empty_one(client, as_role, corpus_mcrit, monkeypatch):
    """getResultForJob answers None both when the job produced no result and when the
    stored document can no longer be retrieved - a purged GridFS entry, a backend
    re-provisioned with the job metadata intact. job_info.result, the result id, is what
    separates them, and it was not being consulted.

    Saying "this job does not contain any data" for a report that merely cannot be
    fetched is a wrong analytical answer in a triage UI, not just wrong wording: it
    reads as "your matching run found nothing".
    """
    as_role("visitor")
    job_id = _with_job(corpus_mcrit, monkeypatch, result="6a7464fcffffffffffffffff")

    response = client.get(f"/data/result/{job_id}")

    assert response.status_code == 200
    assert b"does not contain any data" not in response.data
    assert b"was not found in the system" in response.data


def test_a_job_that_produced_no_result_at_all_says_it_is_empty(client, as_role, corpus_mcrit, monkeypatch):
    """The other side of the same test: no result id means nothing was ever produced."""
    as_role("visitor")
    job_id = _with_job(corpus_mcrit, monkeypatch, result=None)

    response = client.get(f"/data/result/{job_id}")

    assert response.status_code == 200
    assert b"does not contain any data" in response.data


def test_a_report_this_dispatch_cannot_render_is_reported_not_crashed(client, as_role, corpus_mcrit, monkeypatch):
    """The dispatch chain in `data.result` had no else, so a job method it does not
    know - a new one on the backend, say - returned None and Flask answered 500."""
    as_role("visitor")
    job_id = job_id_of("matches_for_sample")
    # deep copy: the corpus client hands out the dict it keeps, and Job wraps it
    job_data = copy.deepcopy(corpus_mcrit.getJobData(job_id)._data)
    job_data["payload"]["method"] = "someFutureMethod"
    monkeypatch.setattr(corpus_mcrit, "getJobData", lambda *args, **kwargs: Job(job_data, None))

    response = client.get(f"/data/result/{job_id}")

    assert response.status_code == 200
    assert b"incompatible with the requested interpretation" in response.data


def test_job_page_renders_for_a_finished_job(client, as_role):
    as_role("visitor")
    response = client.get(f"/data/jobs/{job_id_of('matches_for_sample')}")
    assert response.status_code == 200


if __name__ == "__main__":
    unittest.main()
