#!/usr/bin/python
"""The job page for a job whose payload cannot be read.

`Job.parameters` (mcrit/queue/LocalQueue.py) is not a stored field - it is rebuilt on
every access from `payload["params"]`, by calling `json.loads` on it and then `.items()`
on the result. So a document whose params is a truncated string, the JSON literal
`null`, a JSON array, or simply not a string at all does not yield an empty name: the
property raises JSONDecodeError, AttributeError or TypeError.

`data.job_by_id` used to dereference `job_info.parameters` unconditionally, in
`if 'addBinarySample' in job_info.parameters`, before it had rendered anything - so one
such job turned its own page into a 500. That page is where a great many redirects land
(every job submitter, and any refusal that sends the caller back to the job it was
about), which makes it the wrong page to have no answer for a job the backend will
happily hand out.

The answer is `job_corrupted.html`: the overview itself cannot be rendered, because both
its h1 and the `job_column_table` macro print the parameters, but the job id, the reason,
and a way out can be. `data.result` already answers its own unreadable reports this way
with `result_corrupted.html`.
"""

import logging
import unittest

import pytest
from mcrit.queue.LocalQueue import Job

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

JOB_ID = "0123456789abcdef01234567"

#: Every shape of `payload["params"]` that makes `Job.parameters` raise instead of
#: answering, with the exception each one produces.
MALFORMED_PARAMS = {
    "truncated json": "{not json",          # JSONDecodeError - a half-written document
    "json null": "null",                    # AttributeError  - None has no .items()
    "json array": '[1, "sample.exe"]',      # AttributeError  - a list has no .items()
    "not a string": {"0": 1},               # TypeError       - json.loads wants a str
}


class OneJobBackend:
    """A backend holding exactly one job, whose `params` the test chooses."""

    def __init__(self, params, finished=True):
        self.params = params
        self.finished = finished
        self.calls = []

    def getJobData(self, job_id, *args, **kwargs):
        self.calls.append(("getJobData", job_id))
        if job_id != JOB_ID:
            return None
        return Job({
            "_id": JOB_ID,
            "number": 1,
            "payload": {"method": "getMatchesForSample", "params": self.params,
                        "file_params": "{}", "descriptor": None},
            "all_dependencies": [],
            "created_at": {"$date": "2026-01-01T00:00:00.000Z"},
            "started_at": {"$date": "2026-01-01T00:00:01.000Z"},
            "finished_at": {"$date": "2026-01-01T00:00:02.000Z"} if self.finished else None,
            "last_error": None, "terminated": False, "attempts_left": 3,
            "progress": 1 if self.finished else 0, "result": "r" if self.finished else None,
        }, None)

    def getSampleById(self, *args, **kwargs):
        return None

    def getFamily(self, *args, **kwargs):
        return None


@pytest.fixture
def malformed_job(app, as_role):
    """Wire the app to a backend serving one job with the given `params`, and log in."""
    def _malformed_job(params, finished=True):
        backend = OneJobBackend(params, finished=finished)
        app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: backend
        return backend
    as_role("visitor")
    return _malformed_job


@pytest.mark.parametrize("shape", sorted(MALFORMED_PARAMS))
def test_the_job_page_does_not_crash_on_an_unreadable_payload(client, malformed_job, shape):
    """The bug itself: every one of these was a 500 out of `job_info.parameters`."""
    malformed_job(MALFORMED_PARAMS[shape])

    response = client.get(f"/data/jobs/{JOB_ID}")

    assert response.status_code == 200, f"{shape} still breaks the job page"


@pytest.mark.parametrize("shape", sorted(MALFORMED_PARAMS))
def test_the_job_page_says_the_job_is_corrupted(client, malformed_job, shape):
    """Rendering the overview with a blank name would be a quieter lie than a 500 - the
    page would look like a job that simply has no parameters. `job_corrupted.html` names
    the job and says why there is nothing else to show."""
    malformed_job(MALFORMED_PARAMS[shape])

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "is corrupted" in page
    assert JOB_ID in page


def test_the_corrupted_job_page_offers_a_way_out(client, malformed_job):
    """It is a dead end otherwise - no result to forward to, no overview to fall back
    on. Deleting is a write, so it is a button that POSTs and not a link: a link to a
    POST-only route is a 405 on click and a queued delete on a prefetch (#84)."""
    malformed_job("{not json")

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert 'href="/data/jobs"' in page
    assert 'data-post="/data/jobs/{}/delete"'.format(JOB_ID) in page
    assert 'href="/data/jobs/{}/delete"'.format(JOB_ID) not in page


def test_an_unfinished_unreadable_job_does_not_crash_either(client, malformed_job):
    """The "currently processing" flash reads the parameters too, and it is only reached
    while the job is still running with a refresh set."""
    malformed_job("{not json", finished=False)

    assert client.get(f"/data/jobs/{JOB_ID}?refresh=3").status_code == 200


def test_it_does_not_forward_an_unreadable_job_to_its_result_page(client, malformed_job):
    """`forward=1` is what a submitter sets so the job page hands over to the result as
    soon as the job finishes. `data.result` dispatches on `job_info.parameters` too, so
    forwarding a job whose parameters cannot be read would only move the failure one
    page on - and there is nothing there to show."""
    malformed_job("{not json")

    response = client.get(f"/data/jobs/{JOB_ID}?forward=1")

    assert response.status_code == 200
    assert "is corrupted" in response.get_data(as_text=True)


def test_a_redirect_to_the_job_page_lands_somewhere(client, malformed_job):
    """Every job route ends in `redirect(url_for('data.job_by_id', ...))` - the
    submitters, and any refusal that sends the caller back to the job it was about
    (`/data/jobs/<id>/rerun`, on the branch that adds it, refuses exactly this job).
    A refusal that flashes an error and then lands on a 500 has not refused anything:
    the flash is never rendered. What fixes those paths is this page answering at all,
    so the assertion is that the message survives the landing."""
    malformed_job("{not json")

    with client.session_transaction() as test_session:
        test_session["_flashes"] = [("error", "This job cannot be rerun.")]
    response = client.get(f"/data/jobs/{JOB_ID}?refresh=3", follow_redirects=True)

    assert response.status_code == 200
    assert "This job cannot be rerun." in response.get_data(as_text=True)


def test_a_readable_job_still_renders_its_overview(client, malformed_job):
    """The guard must not swallow the ordinary case: a job with real parameters gets the
    overview, with its name on it."""
    malformed_job('{"0": 1, "1": "readable.exe"}')

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "is corrupted" not in page
    assert "getMatchesForSample(1, readable.exe)" in page


def test_a_job_with_no_parameters_at_all_is_not_called_corrupted(client, malformed_job):
    """`Job.parameters` answers "" - without raising - for a record carrying no `params`
    key, so an empty name is a legitimate answer and not a symptom. Telling those two
    apart is why the recovery cannot simply be `parameters or ""`."""
    backend = malformed_job("{not json")

    def no_payload(job_id, *args, **kwargs):
        backend.calls.append(("getJobData", job_id))
        return Job({"_id": JOB_ID, "number": 1, "payload": {}, "all_dependencies": [],
                    "created_at": {"$date": "2026-01-01T00:00:00.000Z"},
                    "started_at": None, "finished_at": None, "last_error": None,
                    "terminated": False, "attempts_left": 3, "progress": 0, "result": None}, None)
    backend.getJobData = no_payload

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "is corrupted" not in page


if __name__ == "__main__":
    unittest.main()
