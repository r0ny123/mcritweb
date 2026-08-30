#!/usr/bin/python
"""What the job tables say about how long a job took.

A job that waits on dependencies - a cross compare waits on one child per sample -
only starts once the last of them is done, so `Job.duration`, finished_at minus
started_at of the parent, times the assembly of its result and nothing of the work
it is assembled from. `data.total_duration` is the created_at -> finished_at span
that does cover the children; these tests pin it against the captured cross compare
job and over every timestamp shape a job document can carry. See issue #46.
"""

import logging
import re
import unittest
from datetime import UTC, datetime

import pytest
from fixtureData import job_id_of
from mcrit.queue.LocalQueue import Job

from mcritweb.views.data import total_duration

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


def job_table_row(page, label):
    """The value the job table shows for a label, or None if it has no such row.

    The rows are label/value cell pairs:
    <td valign="middle">Duration: </td><td valign="middle"> 0:00:00 </td>
    """
    match = re.search(
        r"<td valign=\"middle\">" + re.escape(label) + r": </td>\s*<td valign=\"middle\">\s*(.*?)\s*</td>",
        page,
        re.S,
    )
    return match.group(1).strip() if match else None


def test_cross_job_page_reports_the_time_its_dependencies_took(client, as_role):
    """A cross compare does not start until every child has finished, so Job.duration
    - finished_at minus started_at of the parent alone - times the assembly of the
    matrix and nothing of the matching that fills it (issue #46). The captured job was
    created at 10:46:10.490 and finished at 10:46:18.572, eight seconds later, and
    reported 0:00:00."""
    as_role("visitor")
    response = client.get(f"/data/jobs/{job_id_of('cross_compare')}")

    assert response.status_code == 200
    page = response.data.decode()
    assert job_table_row(page, "Duration") == "0:00:00"
    assert job_table_row(page, "Total (with dependencies)") == "0:00:08"


def test_cross_result_page_reports_the_total_too(client, as_role):
    """The same table heads the result page, and the same number belongs there."""
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('cross_compare')}")

    assert response.status_code == 200
    assert job_table_row(response.data.decode(), "Total (with dependencies)") == "0:00:08"


def test_a_job_without_dependencies_reports_only_its_own_duration(client, as_role):
    """Nothing waited on, nothing to add - the row stays off the page."""
    as_role("visitor")
    response = client.get(f"/data/jobs/{job_id_of('matches_for_sample')}")

    assert response.status_code == 200
    page = response.data.decode()
    assert job_table_row(page, "Duration") == "0:00:03"
    assert job_table_row(page, "Total (with dependencies)") is None


# --- data.total_duration, over the timestamp shapes a Job can carry ----------------

def job_with(created_at, finished_at, dependencies=("6a7465f2f8b8d2c6f83664c8",)):
    return Job(
        {
            "created_at": created_at,
            "finished_at": finished_at,
            "all_dependencies": list(dependencies),
        },
        None,
    )


@pytest.mark.parametrize(
    "created_at, finished_at",
    [
        # what the REST API sends, and what LocalQueue.Job normalizes it to
        ({"$date": "2026-08-06T10:46:10.490Z"}, {"$date": "2026-08-06T10:46:18.572Z"}),
        ("2026-08-06T10:46:10.490Z", "2026-08-06T10:46:18.572Z"),
        ("2026-08-06 10:46:10.490000", "2026-08-06 10:46:18.572000"),
        (datetime(2026, 8, 6, 10, 46, 10, 490000), datetime(2026, 8, 6, 10, 46, 18, 572000)),
    ],
)
def test_total_duration_reads_every_timestamp_shape(created_at, finished_at):
    assert total_duration(job_with(created_at, finished_at)).total_seconds() == pytest.approx(8, abs=1)


@pytest.mark.parametrize(
    "job",
    [
        pytest.param(job_with("2026-08-06T10:46:10.490Z", "2026-08-06T10:46:18.572Z", dependencies=()), id="no dependencies"),
        pytest.param(job_with("2026-08-06T10:46:10.490Z", None), id="unfinished"),
        pytest.param(job_with(None, "2026-08-06T10:46:18.572Z"), id="never created"),
        pytest.param(job_with("who knows", "2026-08-06T10:46:18.572Z"), id="unparsable"),
        pytest.param(job_with("2026-08-06T10:46", "2026-08-06T10:46:18.572Z"), id="truncated"),
        pytest.param(job_with("2026-08-06T10:46:18.572Z", "2026-08-06T10:46:10.490Z"), id="finished before created"),
        pytest.param(
            job_with(datetime(2026, 8, 6, 10, 46, 10, tzinfo=UTC), datetime(2026, 8, 6, 10, 46, 18)),
            id="one aware one naive",
        ),
        pytest.param(Job({"created_at": "2026-08-06T10:46:10.490Z", "finished_at": "2026-08-06T10:46:18.572Z"}, None), id="no dependency field"),
        pytest.param(Job({"all_dependencies": ["6a7465f2f8b8d2c6f83664c8"], "finished_at": "2026-08-06T10:46:18.572Z"}, None), id="no created_at field"),
        pytest.param(Job({"all_dependencies": ["6a7465f2f8b8d2c6f83664c8"], "created_at": "2026-08-06T10:46:10.490Z"}, None), id="no finished_at field"),
    ],
)
def test_total_duration_has_nothing_to_show(job):
    """Every shape that cannot produce a number renders as no row rather than a 500."""
    assert total_duration(job) is None


if __name__ == "__main__":
    unittest.main()
