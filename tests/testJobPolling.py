#!/usr/bin/python
"""A job page waiting on dependencies polls the job, rather than re-rendering itself.

`data.job_by_id` lists a job's dependencies, and every row needs the dependency and
its sample from the backend, so the overview of a 40-sample cross compare costs 81
backend calls. Opened with `?refresh=3` - which is where every job submitter sends the
browser - it used to meta-refresh and pay all of that every three seconds for as long
as the job ran, mostly to learn that nothing had moved. See issue #183.

What moves is on the job's own document, including `unfinished_dependencies`, which
the queue shrinks as each dependency finishes or finally fails. So the page now polls
`data.job_status_by_id` for that - one call - and reloads when the answer differs from
the one it was rendered from. These tests pin the two halves that make that work: the
poll costs one call however many dependencies there are, and it answers exactly what
the page was rendered from until something the page shows has changed.
"""

import copy
import json
import logging
import re
import unittest

import pytest
from mcrit.queue.LocalQueue import Job

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

#: The size of the cross compare the issue was measured on.
DEPENDENCIES = 40


def job_document(job_id, number, method="getMatchesForSample", params="{}", dependencies=(), unfinished=None, started=True, finished=True, attempts_left=3, progress=None):
    """A job the way the backend sends it, with the fields the overview page reads."""
    return {
        "_id": job_id,
        "number": number,
        # params is a JSON *string* of {index: value}, the way the queue stores it
        "payload": {"method": method, "params": params, "file_params": "{}", "descriptor": None},
        "all_dependencies": list(dependencies),
        "unfinished_dependencies": list(dependencies if unfinished is None else unfinished),
        "created_at": {"$date": "2026-01-01T00:00:00.000Z"},
        "started_at": {"$date": "2026-01-01T00:00:01.000Z"} if started else None,
        "finished_at": {"$date": "2026-01-01T00:00:02.000Z"} if finished else None,
        "last_error": None,
        "terminated": False,
        "attempts_left": attempts_left,
        "progress": (1 if finished else 0) if progress is None else progress,
        "result": "result-id" if finished else None,
    }


def cross_compare(count=DEPENDENCIES, running=True):
    """A cross compare over `count` samples, still waiting on the last of its 1vN jobs."""
    children = [job_document(f"match-{index}", index, params=json.dumps({"0": index})) for index in range(count)]
    children[-1] = job_document(f"match-{count - 1}", count - 1, params=json.dumps({"0": count - 1}), finished=False, progress=0.25)
    parent = job_document(
        "cross", count, "combineMatchesToCross",
        params=json.dumps({"0": {str(index): f"match-{index}" for index in range(count)}}),
        dependencies=[child["_id"] for child in children],
        unfinished=[children[-1]["_id"]] if running else [],
        started=False, finished=False,
    )
    return parent, children


class Queue:
    """A backend holding job documents, recording every call made to it."""

    def __init__(self, *documents):
        self.documents = {document["_id"]: document for document in documents}
        self.calls = []

    def getJobData(self, job_id, *args, **kwargs):
        self.calls.append(("getJobData", job_id))
        document = self.documents.get(job_id)
        return Job(copy.deepcopy(document), None) if document else None

    def getSampleById(self, sample_id, *args, **kwargs):
        self.calls.append(("getSampleById", sample_id))
        return None

    def getFamily(self, family_id, *args, **kwargs):
        self.calls.append(("getFamily", family_id))
        return None


@pytest.fixture
def backend(app, as_role):
    """Install a Queue as the backend, logged in as a visitor, and return it."""
    queue = Queue()
    app.config["MCRIT_CLIENT_FACTORY"] = lambda **kwargs: queue
    as_role("visitor")
    return queue


def rendered_status(html):
    """The status the page will compare every poll against, as it was rendered."""
    embedded = re.search(r"const renderedStatus = JSON\.stringify\((.*?)\);", html)
    return json.loads(embedded.group(1)) if embedded else None


def bare_meta_refresh(html):
    """True if the page reloads itself whether or not JavaScript is running."""
    return 'http-equiv="refresh"' in re.sub(r"<noscript>.*?</noscript>", "", html, flags=re.S)


def test_polling_asks_the_backend_for_the_job_alone(client, backend):
    """The page costs 1 + 2N calls; the poll that stands in for re-rendering it, one."""
    parent, children = cross_compare()
    backend.documents.update({document["_id"]: document for document in [parent] + children})

    response = client.get("/data/jobs/cross/status")

    assert response.status_code == 200
    assert backend.calls == [("getJobData", "cross")], backend.calls


def test_the_page_polls_instead_of_refreshing_while_dependencies_run(client, backend):
    parent, children = cross_compare()
    backend.documents.update({document["_id"]: document for document in [parent] + children})

    html = client.get("/data/jobs/cross?refresh=3").get_data(as_text=True)

    assert "/data/jobs/cross/status" in html, "the page does not poll"
    assert not bare_meta_refresh(html), "the page still re-renders itself every tick"
    # and without JavaScript it keeps the refresh it always had
    assert re.search(r'<noscript><meta http-equiv="refresh" content="3"></noscript>', html)


def test_the_poll_answers_what_the_page_was_rendered_from(client, backend):
    """Otherwise the page would reload on every poll - the old cost with a request on
    top. Both sides come from `data.job_status`, so they can only drift apart if one of
    them stops using it."""
    parent, children = cross_compare()
    backend.documents.update({document["_id"]: document for document in [parent] + children})

    rendered = rendered_status(client.get("/data/jobs/cross?refresh=3").get_data(as_text=True))
    polled = client.get("/data/jobs/cross/status").get_json()["status"]

    assert rendered is not None
    assert polled == rendered


def dependency_finishes(parent, children):
    children[-1].update(job_document(children[-1]["_id"], children[-1]["number"], params=children[-1]["payload"]["params"]))
    parent["unfinished_dependencies"] = []


def dependency_fails(parent, children):
    # the queue pulls a job out of its dependants' unfinished list once its last
    # attempt fails, just as it does when the job finishes
    children[-1]["attempts_left"] = 0
    parent["unfinished_dependencies"] = []


def job_starts(parent, children):
    dependency_finishes(parent, children)
    parent["started_at"] = {"$date": "2026-01-01T00:00:05.000Z"}


def job_progresses(parent, children):
    job_starts(parent, children)
    parent["progress"] = 0.5


def job_finishes(parent, children):
    job_progresses(parent, children)
    parent["finished_at"] = {"$date": "2026-01-01T00:00:06.000Z"}
    parent["progress"] = 1


def job_fails(parent, children):
    parent["attempts_left"] = 0


@pytest.mark.parametrize("change", [dependency_finishes, dependency_fails, job_starts, job_progresses, job_finishes, job_fails])
def test_the_poll_answers_differently_once_the_job_has_moved(client, backend, change):
    """Each of these changes what the page shows, so each has to make it reload."""
    parent, children = cross_compare()
    backend.documents.update({document["_id"]: document for document in [parent] + children})
    rendered = rendered_status(client.get("/data/jobs/cross?refresh=3").get_data(as_text=True))

    change(parent, children)

    assert client.get("/data/jobs/cross/status").get_json()["status"] != rendered


def test_a_job_the_backend_no_longer_has_is_a_404(client, backend):
    """The page reloads on it, and the reload renders job_invalid.html."""
    response = client.get("/data/jobs/0123456789abcdef01234567/status")

    assert response.status_code == 404
    assert response.get_json() == {"status": None}


def test_a_job_without_dependencies_keeps_its_meta_refresh(client, backend):
    """Its page renders from the one call a poll would make, so polling it would only
    add a request."""
    backend.documents["single"] = job_document("single", 1, params='{"0": 7}', finished=False, progress=0.5)

    html = client.get("/data/jobs/single?refresh=3").get_data(as_text=True)

    assert bare_meta_refresh(html)
    assert "/data/jobs/single/status" not in html
    assert client.get("/data/jobs/single/status").get_json() == {"status": None}


def test_a_backend_that_does_not_send_unfinished_dependencies_keeps_the_meta_refresh(client, backend):
    """Nothing to poll for, so the page refreshes the way it always did."""
    parent, children = cross_compare()
    del parent["unfinished_dependencies"]
    backend.documents.update({document["_id"]: document for document in [parent] + children})

    html = client.get("/data/jobs/cross?refresh=3").get_data(as_text=True)

    assert bare_meta_refresh(html)
    assert "/data/jobs/cross/status" not in html


@pytest.mark.parametrize("change", [job_finishes, job_fails])
def test_a_job_that_has_stopped_neither_polls_nor_refreshes(client, backend, change):
    parent, children = cross_compare()
    change(parent, children)
    backend.documents.update({document["_id"]: document for document in [parent] + children})

    html = client.get("/data/jobs/cross?refresh=3").get_data(as_text=True)

    assert not bare_meta_refresh(html)
    assert "/data/jobs/cross/status" not in html
    assert "<noscript><meta" not in html


def test_the_page_polls_only_when_asked_to_refresh(client, backend):
    parent, children = cross_compare()
    backend.documents.update({document["_id"]: document for document in [parent] + children})

    html = client.get("/data/jobs/cross").get_data(as_text=True)

    assert "/data/jobs/cross/status" not in html
    assert 'http-equiv="refresh"' not in html


if __name__ == "__main__":
    unittest.main()
