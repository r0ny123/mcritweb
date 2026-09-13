#!/usr/bin/python
"""The maintenance jobs mcrit 1.9.0 added, and the admin page that can now start them.

`repairMinHashes`, `recomputeFamilyStats` and `rebuildPicBlockHashIndex` are the repairs
for the three things `/status` reports as broken - samples an older smda escaper hashed,
drifted family counters, and the picblockhash index `getUniqueBlocks` reads. Until now
MCRITweb could report all three and start none of them: the server page offers
`rebuildIndex` and `recalculateMinHashes` and nothing else, so an operator had to reach
past the interface to the backend.

Three things had to line up for that to work, and each of them is a separate way to get it
wrong: the route has to queue the job, `data.result()` has to recognise the job type (its
list of maintenance parameters is hand-written, and a job not in it is reported as an
invalid job id), and the template has to render the report rather than "Unhandled
maintenance job type".
"""

import logging

import pytest
from mcrit.queue.LocalQueue import Job

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

JOB_ID = "0123456789abcdef01234567"

#: (route, the client method it queues through)
SCHEDULERS = [
    ("/admin/schedule_repair_minhashes", "repairMinHashes"),
    ("/admin/schedule_recompute_family_stats", "recomputeFamilyStats"),
    ("/admin/schedule_rebuild_picblockhash_index", "rebuildPicBlockHashIndex"),
]

#: every scheduling route on the admin page, old and new
ALL_SCHEDULERS = [path for path, _ in SCHEDULERS] + [
    "/admin/schedule_rebuild_index",
    "/admin/schedule_recalc_minhashes",
    "/admin/schedule_recalc_pichashes",
]

REPORTS = {
    "repairMinHashes()": {
        "compatibility_threshold": "4.4.5",
        "smda_version": "4.5.0",
        "num_samples_stale": 7,
        "num_samples_repaired": 6,
        "num_samples_skipped": 1,
        "num_functions_dropped": 120,
        "num_functions_rehashed": 118,
    },
    "recomputeFamilyStats()": {
        "num_families": 3,
        "num_families_corrected": 1,
        "num_families_created": 2,
        "corrections": {
            "4": {
                "before": {"num_samples": 5, "num_functions": 3, "num_library_samples": 0},
                "after": {"num_samples": 1, "num_functions": 10, "num_library_samples": 0},
            }
        },
    },
    "rebuildPicBlockHashIndex()": 4242,
}


@pytest.fixture
def fake_mcrit(recording_mcrit):
    return recording_mcrit


def call_to(fake, method):
    return next(call for call in fake.calls if call[0] == method)


@pytest.mark.parametrize("path, method", SCHEDULERS)
def test_the_admin_page_can_schedule_the_job(client, as_role, fake_mcrit, path, method):
    as_role("admin")

    response = client.post(path)

    assert call_to(fake_mcrit, method), f"{path} did not queue {method}"
    assert response.status_code == 302
    assert f"/data/jobs/{JOB_ID}" in response.headers["Location"]


@pytest.mark.parametrize("path, method", SCHEDULERS)
def test_the_button_for_it_is_on_the_server_page(client, as_role, path, method):
    as_role("admin")

    page = client.get("/admin/server")

    assert path.encode() in page.data, f"nothing on the server page posts to {path}"


@pytest.mark.parametrize("path", ALL_SCHEDULERS)
def test_a_backend_that_schedules_nothing_is_a_message_not_a_500(client, as_role, fake_mcrit, path):
    """url_for cannot build the redirect without a job id and raises a BuildError, which
    testRoutePolicy caught on two of the new routes. The three older ones had the same hole
    and were only ever saved by the backend answering."""
    as_role("admin")
    fake_mcrit.__dict__.update({name: (lambda *args, **kwargs: None) for name in
                                ("repairMinHashes", "recomputeFamilyStats", "rebuildPicBlockHashIndex",
                                 "rebuildIndex", "recalculateMinHashes", "recalculatePicHashes")})

    response = client.post(path)

    assert response.status_code == 302, f"{path} did not survive a backend that scheduled nothing"
    assert "/admin/server" in response.headers["Location"]
    assert b"did not accept the job" in client.get("/admin/server").data


@pytest.mark.parametrize("parameters", list(REPORTS))
def test_the_result_page_reports_what_the_job_did(client, as_role, fake_mcrit, parameters):
    as_role("admin")
    method = parameters[:-2]
    document = {
        "_id": JOB_ID,
        "payload": {"method": method, "params": "{}", "file_params": {}, "descriptor": method},
        "created_at": "2026-09-13T10:00:00", "started_at": "2026-09-13T10:00:01",
        "finished_at": "2026-09-13T10:00:09", "last_error": None, "terminated": False,
        "attempts_left": 3, "progress": 1, "number": 1, "result": "deadbeef",
        "all_dependencies": [], "unfinished_dependencies": [],
    }
    fake_mcrit.__dict__["getJobData"] = lambda job_id, *a, **k: Job(document, None)
    fake_mcrit.__dict__["getResultForJob"] = lambda job_id, *a, **k: REPORTS[parameters]

    response = client.get(f"/data/result/{JOB_ID}")

    assert response.status_code == 200
    assert b"Unhandled maintenance job type" not in response.data, f"{parameters} is not rendered"
    assert b"seems to be invalid" not in response.data and b"result_invalid" not in response.data


def test_the_repair_report_names_the_samples_it_could_not_rehash(client, as_role, fake_mcrit):
    """A skipped sample keeps its old minhashes because its disassembly is gone; a report that
    only showed "repaired" would read as a clean run over a corpus that still has stale ones."""
    as_role("admin")
    document = {
        "_id": JOB_ID,
        "payload": {"method": "repairMinHashes", "params": "{}", "file_params": {}, "descriptor": "repairMinHashes"},
        "created_at": "2026-09-13T10:00:00", "started_at": "2026-09-13T10:00:01",
        "finished_at": "2026-09-13T10:00:09", "last_error": None, "terminated": False,
        "attempts_left": 3, "progress": 1, "number": 1, "result": "deadbeef",
        "all_dependencies": [], "unfinished_dependencies": [],
    }
    fake_mcrit.__dict__["getJobData"] = lambda job_id, *a, **k: Job(document, None)
    fake_mcrit.__dict__["getResultForJob"] = lambda job_id, *a, **k: REPORTS["repairMinHashes()"]

    page = client.get(f"/data/result/{JOB_ID}").data

    assert b"skipped" in page
    assert b"1" in page and b"118" in page
