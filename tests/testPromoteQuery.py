#!/usr/bin/python
"""Promoting a query to a stored sample - issue #9.

A query is matched without being stored: the backend answers with `sample_id: -1`,
no family and no version, and nothing about it stays in the corpus. Promotion turns
one into a real sample without asking the analyst to find the file and upload it a
second time.

Where the bytes come from is the whole story, so it is worth writing down. The
backend keeps a query's input in GridFS behind a job reference and exposes no route
that reads it back - `application_routes.py` has `/jobs/{id}`, `/jobs/{id}/result`
and `/results/{id}`, and nothing for a job's *input* - and `McritClient` has no verb
that turns a query job into a sample. The only copy that can be resubmitted is the
one `analyze.query` writes into `instance/temp/uploads/<sha256>`, named by the
sha256 of the queried *sample* - which is what the query's report records, and not
always what the job descriptor holds.

That copy is local to a single host and is written by the web upload alone:
`api.api_router` forwards a query straight to the backend, so a query from the API or
the IDA plugin never leaves one. Promotion is therefore offered exactly when the file
is there, and says so plainly when it is not, instead of presenting a button that
fails.
"""

import builtins
import copy
import hashlib
import json
import logging
import pathlib
import unittest

import pytest
from fixtureData import job_id_of, load
from mcrit.storage.SampleEntry import SampleEntry

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

#: The synthetic query jobs below all live under this id, so a test names one place.
QUERY_JOB_ID = "0123456789abcdef01234567"

#: What the backend answers when a promotion queues work.
NEW_JOB_ID = "fedcba9876543210fedcba98"

#: Bytes small enough to keep in a fixture and real enough to hash.
QUERIED_BYTES = b"MZ" + bytes(range(256)) * 4

#: An entry to stand in for what `addReport` gives back - a real one out of the
#: corpus, because the view reads `.sample_id` off it to build a redirect.
PROMOTED_SAMPLE = SampleEntry.fromDict(next(iter(load("samples").values())))


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """The captured corpus, taught the two write verbs a promotion reaches for.

    `CorpusMcritClient` raises NotImplementedError for anything nobody taught it,
    which is the right default everywhere else. Here the writes are exactly what these
    tests assert on, so they have to be recorded rather than raised.
    """
    def _add_binary_sample(binary, **kwargs):
        corpus_mcrit._record("addBinarySample", binary, **kwargs)
        return NEW_JOB_ID

    def _add_report(smda_report, *args, **kwargs):
        corpus_mcrit._record("addReport", smda_report, *args, **kwargs)
        return PROMOTED_SAMPLE, NEW_JOB_ID

    corpus_mcrit.addBinarySample = _add_binary_sample
    corpus_mcrit.addReport = _add_report
    return corpus_mcrit


@pytest.fixture
def uploads(app):
    """The directory `analyze.query` keeps its copy of an uploaded query in."""
    return pathlib.Path(app.instance_path) / "temp" / "uploads"


def register_query(backend, method="getMatchesForUnmappedBinary", digest=None,
                   base_address=31850496, bitness=32, job_id=QUERY_JOB_ID):
    """Put a query job, and the report it produced, into the backend.

    The captured query job is the template, and the report is where the sample's
    sha256 comes from - `analyze.query` names its stored copy by that, and it is the
    only value that means the same thing for all three upload kinds. The descriptor
    carries a *different* hash for an .smda query: `QueueRemoteCalls` hashes the
    canonicalised JSON it serialised, not the sample it describes. This fixture
    reproduces that, so a promotion that read the file hash out of the descriptor
    would find nothing for an .smda upload.
    """
    if digest is None:
        digest = hashlib.sha256(QUERIED_BYTES).hexdigest()
    document = copy.deepcopy(load("matches_for_query.job"))
    document["_id"] = {"$oid": job_id}
    params = {"band_matches_required": 2, "0": None, "1": base_address}
    document["payload"]["method"] = method
    document["payload"]["params"] = json.dumps(params)
    descriptor_hash = hashlib.sha256(job_id.encode()).hexdigest() if method == "getMatchesForSmdaReport" else digest
    document["payload"]["descriptor"] = json.dumps([method, params, {"0": descriptor_hash}])

    report = copy.deepcopy(load("matches_for_query.result"))
    report["info"]["sample"]["sha256"] = digest
    report["info"]["sample"]["base_addr"] = base_address
    report["info"]["sample"]["bitness"] = bitness

    backend._jobs[job_id] = (document, report)
    return digest


def smda_upload(sha256, family="", version=""):
    """An SMDA report as the .smda branch of `analyze.query` stored it: the uploaded
    JSON itself, under the sha256 the *report* claims, not the hash of the JSON."""
    return json.dumps({
        "architecture": "intel", "abi": "cdecl", "base_addr": 4194304,
        "binary_size": 2371584, "bitness": 32, "code_areas": [], "code_sections": [],
        "confidence_threshold": 0.5, "disassembly_errors": {}, "execution_time": 1.0,
        "identified_alignment": 16,
        "metadata": {
            "binweight": 1234, "component": "", "family": family, "filename": "query.exe",
            "is_library": False, "is_buffer": False, "language": "C", "version": version,
        },
        "message": "", "oep": 4198400, "sha256": sha256, "smda_version": "4.4.4",
        "statistics": {}, "status": "ok", "timestamp": "2026-08-07T12-00-00", "xcfg": {},
    }).encode()


def promote(client, job_id=QUERY_JOB_ID, **fields):
    """POST the promotion form the result page renders."""
    data = {"family": "test.family", "version": "1.0"}
    data.update(fields)
    return client.post(f"/data/promote_query/{job_id}", data=data)


def calls_to(backend, method):
    return [call for call in backend.calls if call[0] == method]


def wrote_nothing(backend):
    """No sample reached the corpus, by either of the two routes into it."""
    return not calls_to(backend, "addBinarySample") and not calls_to(backend, "addReport")


# --- what the result page offers ---------------------------------------------------

def test_the_query_result_page_offers_promotion_while_the_upload_is_here(client, as_role, uploads):
    """The captured query report, with its uploaded file still in place. This is the
    only state in which the button is honest, so it is the only state that shows it."""
    as_role("contributor")
    report_sha256 = load("matches_for_query.result")["info"]["sample"]["sha256"]
    (uploads / report_sha256).write_bytes(QUERIED_BYTES)

    page = client.get(f"/data/result/{job_id_of('matches_for_query')}").get_data(as_text=True)
    assert f'action="/data/promote_query/{job_id_of("matches_for_query")}"' in page


def test_the_query_result_page_explains_itself_when_the_upload_is_gone(client, as_role):
    """A query from the API, from the IDA plugin, or from another host of the same
    deployment leaves no local copy. Offering a button that cannot work would be the
    worse answer, so the page says why instead."""
    as_role("contributor")

    page = client.get(f"/data/result/{job_id_of('matches_for_query')}").get_data(as_text=True)
    assert "/data/promote_query/" not in page
    assert "no longer available on this server" in page


def test_a_visitor_is_not_offered_promotion(client, as_role, uploads):
    """Promotion adds to the corpus, which is contributor work - `data.submit` draws
    the same line. The route enforces it; the page must not dangle it either."""
    as_role("visitor")
    report_sha256 = load("matches_for_query.result")["info"]["sample"]["sha256"]
    (uploads / report_sha256).write_bytes(QUERIED_BYTES)

    page = client.get(f"/data/result/{job_id_of('matches_for_query')}").get_data(as_text=True)
    assert "/data/promote_query/" not in page


def test_a_sample_result_page_offers_no_promotion(client, as_role):
    """`getMatchesForSample` matched something the corpus already holds. There is
    nothing to promote, and the same template renders both."""
    as_role("contributor")

    page = client.get(f"/data/result/{job_id_of('matches_for_sample')}").get_data(as_text=True)
    assert "/data/promote_query/" not in page
    assert "no longer available on this server" not in page


# --- what a promotion submits ------------------------------------------------------

def test_promotion_resubmits_the_bytes_that_were_queried(client, as_role, fake_mcrit, uploads):
    """The point of the feature: the corpus gets the same file that was matched, with
    the family and version the analyst decided on afterwards."""
    as_role("contributor")
    digest = register_query(fake_mcrit)
    (uploads / digest).write_bytes(QUERIED_BYTES)

    response = promote(client)

    assert response.status_code == 302
    _, args, kwargs = calls_to(fake_mcrit, "addBinarySample")[0]
    assert args[0] == QUERIED_BYTES
    assert kwargs["family"] == "test.family"
    assert kwargs["version"] == "1.0"
    assert kwargs["is_dump"] is False


def test_the_promoted_sample_is_reached_through_its_job(client, as_role, fake_mcrit, uploads):
    """`addBinarySample` only queues disassembly, so there is no sample id yet - the
    same hop `data.submit` makes."""
    as_role("contributor")
    digest = register_query(fake_mcrit)
    (uploads / digest).write_bytes(QUERIED_BYTES)

    response = promote(client)
    assert f"/data/jobs/{NEW_JOB_ID}" in response.headers["Location"]


def test_a_mapped_query_is_promoted_as_the_dump_it_was(client, as_role, fake_mcrit, uploads):
    """A dump has to be resubmitted with the base address and bitness it was queried
    under. The backend defaults bitness to 32 when it is not told, so a 64-bit dump
    promoted without it would be disassembled differently than the report on screen."""
    as_role("contributor")
    digest = register_query(fake_mcrit, method="getMatchesForMappedBinary",
                            base_address=0x140000000, bitness=64)
    (uploads / digest).write_bytes(QUERIED_BYTES)

    promote(client)

    _, _, kwargs = calls_to(fake_mcrit, "addBinarySample")[0]
    assert kwargs["is_dump"] is True
    assert kwargs["base_addr"] == 0x140000000
    assert kwargs["bitness"] == 64


def test_an_smda_query_is_promoted_through_its_report(client, as_role, fake_mcrit, uploads):
    """An .smda upload is not a binary, so it goes back the way `data.submit` sends
    one - as a report. Family and version have nowhere else to go than into it."""
    as_role("contributor")
    digest = "ab" * 32
    register_query(fake_mcrit, method="getMatchesForSmdaReport", digest=digest)
    (uploads / digest).write_bytes(smda_upload(digest))

    response = promote(client)

    assert not calls_to(fake_mcrit, "addBinarySample")
    _, args, _ = calls_to(fake_mcrit, "addReport")[0]
    assert args[0].sha256 == digest
    assert args[0].family == "test.family"
    assert args[0].version == "1.0"
    assert f"/explore/samples/{PROMOTED_SAMPLE.sample_id}" in response.headers["Location"]


def test_an_smda_query_is_found_by_the_sample_hash_not_the_descriptor_hash(client, as_role, fake_mcrit, uploads):
    """Which hash names the stored upload is not obvious, and getting it wrong is
    silent. `analyze.query` files every upload under the sha256 of the *sample*, while
    the job descriptor holds the hash of whatever `QueueRemoteCalls` serialised - for
    an .smda query that is the canonicalised report JSON, so the two differ. Reading
    the descriptor would report every .smda query as no longer available."""
    as_role("contributor")
    digest = "ab" * 32
    register_query(fake_mcrit, method="getMatchesForSmdaReport", digest=digest)
    descriptor = json.loads(fake_mcrit._jobs[QUERY_JOB_ID][0]["payload"]["descriptor"])
    assert descriptor[2]["0"] != digest, "the fixture no longer reproduces the two hashes"
    (uploads / digest).write_bytes(smda_upload(digest))

    promote(client)

    assert calls_to(fake_mcrit, "addReport"), "the upload was not found under the sample hash"


def test_an_smda_report_keeps_its_own_family_when_none_is_typed(client, as_role, fake_mcrit, uploads):
    """An empty form field means "say nothing", not "erase what the report carries"."""
    as_role("contributor")
    digest = "ab" * 32
    register_query(fake_mcrit, method="getMatchesForSmdaReport", digest=digest)
    (uploads / digest).write_bytes(smda_upload(digest, family="win.citadel", version="2019"))

    promote(client, family="", version="")

    _, args, _ = calls_to(fake_mcrit, "addReport")[0]
    assert args[0].family == "win.citadel"
    assert args[0].version == "2019"


# --- what a promotion refuses ------------------------------------------------------

def test_promoting_a_query_that_is_already_in_the_corpus_creates_nothing(client, as_role, fake_mcrit, uploads):
    """Promoting twice must not make two samples. The corpus is checked by hash before
    anything is submitted, and the second attempt lands on the sample that exists."""
    as_role("contributor")
    known = next(iter(fake_mcrit._samples.values()))
    register_query(fake_mcrit, digest=known.sha256)
    (uploads / known.sha256).write_bytes(QUERIED_BYTES)

    response = promote(client)

    assert wrote_nothing(fake_mcrit)
    assert f"/explore/samples/{known.sample_id}" in response.headers["Location"]


def test_the_corpus_is_checked_even_once_the_local_copy_is_gone(client, as_role, fake_mcrit):
    """"Already promoted" is the true answer whether or not the upload survived, so it
    is answered first. Reporting a missing file for a sample that is plainly in the
    database would send the analyst looking for it again."""
    as_role("contributor")
    known = next(iter(fake_mcrit._samples.values()))
    register_query(fake_mcrit, digest=known.sha256)

    response = promote(client)

    assert wrote_nothing(fake_mcrit)
    assert f"/explore/samples/{known.sample_id}" in response.headers["Location"]


def test_promotion_without_the_local_copy_writes_nothing(client, as_role, fake_mcrit):
    """The gate the template shows must also hold in the route: a hand-made POST for a
    query whose bytes are gone has to be refused, not guessed at."""
    as_role("contributor")
    register_query(fake_mcrit)

    response = promote(client)

    assert response.status_code == 302
    assert wrote_nothing(fake_mcrit)


def test_promotion_of_a_job_that_is_not_a_query_writes_nothing(client, as_role, fake_mcrit):
    """Every other job id in the system is one POST away. None of them describe an
    upload this host still has, so none of them may promote anything."""
    as_role("contributor")

    response = promote(client, job_id=job_id_of("matches_for_sample"))

    assert response.status_code == 302
    assert wrote_nothing(fake_mcrit)


def test_promotion_of_a_job_nobody_knows_writes_nothing(client, as_role, fake_mcrit):
    as_role("contributor")

    response = promote(client, job_id="ffffffffffffffffffffffff")

    assert response.status_code == 302
    assert wrote_nothing(fake_mcrit)


def test_a_local_copy_that_no_longer_matches_the_query_is_not_submitted(client, as_role, fake_mcrit, uploads):
    """The file is named by the hash of the query's input, so a file whose contents
    hash to something else is not that input. Promoting it would put a different
    sample in the corpus under a report that never described it."""
    as_role("contributor")
    digest = register_query(fake_mcrit)
    (uploads / digest).write_bytes(b"something else entirely")

    response = promote(client)

    assert response.status_code == 302
    assert wrote_nothing(fake_mcrit)


def test_an_smda_upload_that_describes_another_sample_is_not_submitted(client, as_role, fake_mcrit, uploads):
    """The same check on the .smda path, where the hash lives inside the report rather
    than over the bytes."""
    as_role("contributor")
    digest = "ab" * 32
    register_query(fake_mcrit, method="getMatchesForSmdaReport", digest=digest)
    (uploads / digest).write_bytes(smda_upload("cd" * 32))

    response = promote(client)

    assert response.status_code == 302
    assert wrote_nothing(fake_mcrit)


@pytest.mark.parametrize("payload", [b"not json at all", b'["a", "list"]', b"{}"])
def test_an_unreadable_smda_upload_is_reported_rather_than_a_500(client, as_role, fake_mcrit, uploads, payload):
    """Whatever sits in the uploads directory is an uploaded file, which is to say
    attacker-controlled. Anything it does to the parser has to become a message."""
    as_role("contributor")
    digest = "ab" * 32
    register_query(fake_mcrit, method="getMatchesForSmdaReport", digest=digest)
    (uploads / digest).write_bytes(payload)

    response = promote(client)

    assert response.status_code < 500
    assert wrote_nothing(fake_mcrit)


@pytest.mark.parametrize("field", ["family", "version"])
def test_metadata_that_could_inject_backend_parameters_is_refused(client, as_role, fake_mcrit, uploads, field):
    """`McritClient.addBinarySample` builds its request by pasting these into a query
    string without percent-encoding, so a value carrying '&' would append parameters
    of its own to the backend call - `is_dump`, or another `family`. Nothing shaped
    like that gets that far."""
    as_role("contributor")
    digest = register_query(fake_mcrit)
    (uploads / digest).write_bytes(QUERIED_BYTES)

    response = promote(client, **{field: "evil&is_dump=1&family=other"})

    assert response.status_code == 302
    assert wrote_nothing(fake_mcrit)


def test_a_report_without_a_usable_hash_promotes_nothing(client, as_role, fake_mcrit, uploads, monkeypatch):
    """The sha256 becomes a filename, so it only does so once it is a sha256. A report
    that names something else must not be able to reach out of the uploads folder.

    Asserting that nothing was submitted is not enough here: with the hash check
    removed, the traversal succeeds, the file is read, and the promotion is then
    rejected further down because the bytes do not hash to the "digest". That leaves
    an arbitrary-file-read behind a passing test - and, on the .smda branch, an
    arbitrary file parsed as JSON. So this asserts the file is never opened at all.
    """
    as_role("contributor")
    # a target outside the uploads folder, reached by exactly as many steps as it
    # takes - a fixed "../../../../etc/passwd" only traverses on a filesystem where
    # the instance path happens to sit four levels down, so it would pass anywhere
    # else for no reason at all
    outside = uploads.parent.parent / "outside.txt"
    outside.write_bytes(b"not an upload")
    register_query(fake_mcrit, digest="../../" + outside.name)
    (uploads / "sample").write_bytes(QUERIED_BYTES)

    opened = []
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda file, *args, **kwargs: (opened.append(file), real_open(file, *args, **kwargs))[1])

    response = promote(client)

    assert response.status_code == 302
    assert wrote_nothing(fake_mcrit)
    assert not [path for path in opened if outside.name in str(path)], f"read outside the uploads folder: {opened}"


def test_promotion_is_not_reachable_by_get(client, as_role, fake_mcrit, uploads):
    """Issue #84: a write a browser performs on plain navigation is reachable from any
    page the victim visits, and carries no CSRF token to check."""
    as_role("contributor")
    digest = register_query(fake_mcrit)
    (uploads / digest).write_bytes(QUERIED_BYTES)

    response = client.get(f"/data/promote_query/{QUERY_JOB_ID}")

    assert response.status_code == 405
    assert wrote_nothing(fake_mcrit)


def test_promotion_needs_a_contributor(client, as_role, fake_mcrit, uploads):
    """The same floor `data.submit` stands on, enforced in the route rather than only
    in the template that hides the form."""
    as_role("visitor")
    digest = register_query(fake_mcrit)
    (uploads / digest).write_bytes(QUERIED_BYTES)

    response = promote(client)

    assert response.status_code == 403
    assert wrote_nothing(fake_mcrit)


if __name__ == "__main__":
    unittest.main()
