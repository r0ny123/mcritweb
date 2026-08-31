#!/usr/bin/python
"""Job pages holding a job whose payload cannot be read.

`Job.parameters` (mcrit/queue/LocalQueue.py) is not a stored field - it is rebuilt on
every access from `payload["params"]`, by calling `json.loads` on it and then `.items()`
on the result. So a document whose params is a truncated string, the JSON literal
`null`, a JSON array, or simply not a string at all does not yield an empty name: the
property raises JSONDecodeError, AttributeError or TypeError. `arguments`, `sample_ids`
and `family_id` are rebuilt from the same place and raise with it, so almost everything
a job page shows about a job past its method name is unavailable at once.

Two pages have to survive that.

`data.job_by_id` dereferenced `job_info.parameters` unconditionally, in
`if 'addBinarySample' in job_info.parameters`, so a job whose own payload was unreadable
turned its own page into a 500. That page is where a great many redirects land - every
job submitter, and any route that refuses a job and sends the caller back to it - which
makes it the wrong page to have no answer for a job the backend hands out happily. It
answers with `job_corrupted.html`, the sibling of the `result_corrupted.html` that
`data.result` already answers its own unreadable reports with.

A job page also lists other jobs: its dependencies on `job_overview.html`, the queue on
`jobs.html`. There one unreadable job must not take down the page it appears on, which
is about the other jobs - so the row is rendered as unreadable and its neighbours are
unaffected. That degrades in two places, because both the `sample_ids`/`family_id`
lookups in the view and the `job_description` macro read the same payload.
"""

import logging
import unittest

import pytest
from mcrit.queue.LocalQueue import Job

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

JOB_ID = "0123456789abcdef01234567"
CHILD_ID = "0123456789abcdef0123beef"

#: Every shape of `payload["params"]` that makes `Job.parameters` raise instead of
#: answering, with the exception each one produces.
MALFORMED_PARAMS = {
    "truncated json": "{not json",          # JSONDecodeError - a half-written document
    "json null": "null",                    # AttributeError  - None has no .items()
    "json array": '[1, "sample.exe"]',      # AttributeError  - a list has no .items()
    "not a string": {"0": 1},               # TypeError       - json.loads wants a str
}


def job_document(job_id, params, method="getMatchesForSample", number=1,
                 dependencies=(), finished=True):
    """One job record in the shape mcrit's Job wraps."""
    return {
        "_id": job_id,
        "number": number,
        "payload": {"method": method, "params": params, "file_params": "{}",
                    "descriptor": None},
        "all_dependencies": list(dependencies),
        "created_at": {"$date": "2026-01-01T00:00:00.000Z"},
        "started_at": {"$date": "2026-01-01T00:00:01.000Z"},
        "finished_at": {"$date": "2026-01-01T00:00:02.000Z"} if finished else None,
        "last_error": None, "terminated": False, "attempts_left": 3,
        "progress": 1 if finished else 0, "result": "r" if finished else None,
    }


class JobsBackend:
    """A backend serving a fixed set of job documents, by id and as the whole queue."""

    def __init__(self, documents):
        self.documents = {document["_id"]: document for document in documents}
        self.calls = []

    def getJobData(self, job_id, *args, **kwargs):
        self.calls.append(("getJobData", job_id))
        document = self.documents.get(job_id)
        return Job(document, None) if document else None

    def getQueueData(self, *args, **kwargs):
        self.calls.append(("getQueueData", args, kwargs))
        return [Job(document, None) for document in self.documents.values()]

    def getQueueStatistics(self, *args, **kwargs):
        return {"getMatchesForSample": {"finished": len(self.documents)}}

    def getSampleById(self, *args, **kwargs):
        return None

    def getFamily(self, *args, **kwargs):
        return None


@pytest.fixture
def backend(app, as_role):
    """Wire the app to a backend serving the given job documents, and log in."""
    def _backend(documents, role="visitor"):
        instance = JobsBackend(documents)
        app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: instance
        as_role(role)
        return instance
    return _backend


@pytest.fixture
def malformed_job(backend):
    """The single-job case: one job, whose `params` the test chooses."""
    def _malformed_job(params, finished=True, role="visitor"):
        return backend([job_document(JOB_ID, params, finished=finished)], role=role)
    return _malformed_job


# --- the job's own page --------------------------------------------------------


@pytest.mark.parametrize("shape", sorted(MALFORMED_PARAMS))
def test_the_job_page_does_not_crash_on_an_unreadable_payload(client, malformed_job, shape):
    """The bug itself: every one of these was a 500 out of `job_info.parameters`."""
    malformed_job(MALFORMED_PARAMS[shape])

    response = client.get(f"/data/jobs/{JOB_ID}")

    assert response.status_code == 200, f"{shape} still breaks the job page"


@pytest.mark.parametrize("shape", sorted(MALFORMED_PARAMS))
def test_the_job_page_says_the_job_is_corrupted(client, malformed_job, shape):
    """Rendering the overview anyway would be a 500 for the two shapes that raise a
    JSONDecodeError or TypeError out of Jinja, and for the other two a quieter lie:
    Jinja's getattr swallows an AttributeError, so the page would come out looking like
    a job that simply has no parameters. `job_corrupted.html` names the job instead and
    says why there is nothing else to show."""
    malformed_job(MALFORMED_PARAMS[shape])

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "is corrupted" in page
    assert JOB_ID in page


def test_the_corrupted_job_page_offers_a_way_out_to_someone_who_can_take_it(client, malformed_job):
    """It is a dead end otherwise - no result to forward to, no overview to fall back
    on. Deleting is a write, so it is a button that POSTs and not a link: a link to a
    POST-only route is a 405 on click and a queued delete on a prefetch (#84)."""
    malformed_job("{not json", role="contributor")

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert 'href="/data/jobs"' in page
    assert 'data-post="/data/jobs/{}/delete"'.format(JOB_ID) in page
    assert 'href="/data/jobs/{}/delete"'.format(JOB_ID) not in page


def test_a_visitor_is_not_offered_a_delete_they_cannot_perform(client, malformed_job):
    """This page is `visitor_required` and `delete_job_by_id` is `contributor_required`,
    so an ungated button is a 403 waiting to happen - and on a page whose whole purpose
    is to offer the one action still available for this job, an offer that fails is
    worse than none. The way back to the job list is still there for them."""
    malformed_job("{not json", role="visitor")

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "is corrupted" in page
    assert 'href="/data/jobs"' in page
    assert "/delete" not in page


def test_an_unfinished_unreadable_job_does_not_crash_either(client, malformed_job):
    """The "currently processing" flash reads the parameters too, and it is only reached
    while the job is still running with a refresh set."""
    malformed_job("{not json", finished=False)

    assert client.get(f"/data/jobs/{JOB_ID}?refresh=3").status_code == 200


def test_it_does_not_auto_forward_an_unreadable_job_to_its_result_page(client, malformed_job):
    """`forward=1` is what a submitter sets so the job page hands over to the result as
    soon as the job finishes. `data.result` dispatches on `job_info.parameters` too and
    is not guarded, so auto-forwarding a job whose parameters cannot be read would only
    move the failure one page on - and there is nothing there to show. Someone who
    types the result URL still gets that 500; this only closes the automatic path."""
    malformed_job("{not json")

    response = client.get(f"/data/jobs/{JOB_ID}?forward=1")

    assert response.status_code == 200
    assert "is corrupted" in response.get_data(as_text=True)


def test_a_flash_survives_onto_the_corrupted_page(client, malformed_job):
    """Every job route ends in `redirect(url_for('data.job_by_id', ...))` - the
    submitters, and any route that refuses a job and sends the caller back to it
    (`/data/jobs/<id>/rerun`, on the branch that adds it, refuses exactly this job).
    A refusal that flashes an error and then lands on a 500 has not refused anything,
    because the message is never rendered. So what this page owes those callers is not
    only a status code but the message they set."""
    malformed_job("{not json")

    with client.session_transaction() as test_session:
        test_session["_flashes"] = [("error", "This job cannot be rerun.")]
    response = client.get(f"/data/jobs/{JOB_ID}")

    assert response.status_code == 200
    assert "This job cannot be rerun." in response.get_data(as_text=True)


def test_a_readable_job_still_renders_its_overview(client, malformed_job):
    """The guard must not swallow the ordinary case: a job with real parameters gets the
    overview, with its name on it."""
    malformed_job('{"0": 1, "1": "readable.exe"}')

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "is corrupted" not in page
    assert "getMatchesForSample(1, readable.exe)" in page


def test_a_job_with_no_parameters_at_all_is_not_called_corrupted(client, backend):
    """`Job.parameters` answers "" - without raising - for a record carrying no `params`
    key, so an empty name is a legitimate answer and not a symptom. Telling those two
    apart is why the recovery cannot simply be `parameters or ""`."""
    document = job_document(JOB_ID, "{}")
    document["payload"] = {}
    backend([document])

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "is corrupted" not in page


def test_an_unexpected_error_is_not_reported_as_a_corrupt_payload(client, backend):
    """The recovery catches what mcrit can raise out of this payload - a JSONDecodeError
    (a ValueError), an AttributeError, a TypeError - and nothing else. A bare
    `except Exception` would turn a future bug in `Job` into a page calmly reporting
    that everybody's jobs are corrupt, which is both wrong and unreportable."""
    backend([job_document(JOB_ID, "{}")])

    class BrokenJob:
        job_id = JOB_ID

        @property
        def parameters(self):
            raise KeyError("number")

    with client.application.test_request_context():
        from mcritweb.views.data import job_parameters_or_none

        with pytest.raises(KeyError):
            job_parameters_or_none(BrokenJob())


# --- other jobs listed on a job page -------------------------------------------


@pytest.fixture
def parent_with_bad_child(backend):
    """A healthy cross compare whose one dependency has an unreadable payload."""
    def _parent_with_bad_child(child_params="{not json", child_method="getMatchesForSample"):
        return backend([
            job_document(JOB_ID, '{"0": {"1": "a"}}', method="combineMatchesToCross",
                         number=2, dependencies=[CHILD_ID]),
            job_document(CHILD_ID, child_params, method=child_method, number=1),
        ])
    return _parent_with_bad_child


def test_a_healthy_parent_survives_an_unreadable_child(client, parent_with_bad_child):
    """The parent's own payload is fine, so guarding only `job_info.parameters` moved
    the 500 rather than closing it: `job.sample_ids` and `job.family_id` are rebuilt
    from the child's params in the view, and `job_description` reads them again in the
    row. A cross compare with one corrupt child job broke on the parent's page."""
    parent_with_bad_child()

    response = client.get(f"/data/jobs/{JOB_ID}")

    assert response.status_code == 200
    assert "is corrupted" not in response.get_data(as_text=True), "the parent is fine"


def test_the_unreadable_child_is_shown_rather_than_hidden(client, parent_with_bad_child):
    """Dropping the row would misreport how many jobs the cross compare ran. Everything
    the row shows besides the description - number, timestamps, progress, the job id it
    links to - comes from fields that do not touch the payload, so the row is still
    worth rendering and still leads somewhere."""
    parent_with_bad_child()

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "payload unreadable" in page
    assert CHILD_ID in page


@pytest.mark.parametrize("method", ["getMatchesForSample", "getMatchesForSampleVsGroup"])
def test_the_child_guard_covers_both_places_it_can_break(client, parent_with_bad_child, method):
    """Which one raises first depends on the child's method: `sample_ids` consults
    `arguments` for a matching job and breaks in the view, while a method `job_row`
    has no branch for reaches the macro's `{{ job.parameters }}` fallback and breaks in
    the template. `getMatchesForSampleVsGroup` is the second case and not a contrived
    one - it is what a cross compare runs its children as, and #51 added it to the job
    listing without adding a row for it."""
    parent_with_bad_child(child_method=method)

    assert client.get(f"/data/jobs/{JOB_ID}").status_code == 200


def test_a_readable_child_is_still_described(client, backend):
    """The row guard must not blank out healthy children."""
    backend([
        job_document(JOB_ID, '{"0": {"1": "a"}}', method="combineMatchesToCross",
                     number=2, dependencies=[CHILD_ID]),
        job_document(CHILD_ID, '{"0": 7}', method="getMatchesForSample", number=1),
    ])

    page = client.get(f"/data/jobs/{JOB_ID}").get_data(as_text=True)

    assert "payload unreadable" not in page
    assert "Match 1vN" in page


def test_the_browse_list_survives_an_unreadable_job(client, backend):
    """The same two breakages, on the page that lists the queue. This is the page the
    job search was already made safe for by filtering unreadable jobs out of a search;
    browsing shows them, so browsing has to render them."""
    backend([
        job_document(JOB_ID, '{"0": 7}', method="getMatchesForSample", number=1),
        job_document(CHILD_ID, "{not json", method="getMatchesForSample", number=2),
    ])

    response = client.get("/data/jobs?active=getMatchesForSample")

    assert response.status_code == 200
    assert "payload unreadable" in response.get_data(as_text=True)
    assert "Match 1vN" in response.get_data(as_text=True), "its neighbour is unaffected"


if __name__ == "__main__":
    unittest.main()
