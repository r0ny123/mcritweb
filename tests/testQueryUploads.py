#!/usr/bin/python
"""How `analyze.query` names the file it keeps under `instance/temp/uploads/`.

The route is `@visitor_required` and writes every upload to
`instance/temp/uploads/<name>` with mode "wb" and no existence check, so the name is
the only thing standing between two users' uploads. For the two binary branches the
name is `sha256(binary_content)` - a digest of the bytes that were actually posted,
which nobody can choose without producing the matching bytes. For the `.smda` branch
it was taken from the report's own `sha256` field instead: a number the uploader
types into a JSON file.

That made one visitor's upload able to land on top of another user's stored query.
Nothing here reads those files back yet - the promote-to-sample path that does lives
on a sibling branch - so the damage is only visible as the file content, which is
exactly what these tests look at. A stored query that has quietly become somebody
else's JSON is wrong whether or not this branch has the reader that trips over it.

The fix is to name a `.smda` upload the way the other two kinds are already named, by
the digest of the uploaded bytes. That leaves one collision - two users uploading the
same bytes - and `test_the_same_bytes_from_two_users...` is here to show what happens
in it, rather than leaving it asserted.

Not covered here, because naming does not answer it: the directory is still never
pruned, and an attacker who varies any byte still gets one more file per request. The
per-role size cap in QUERY_UPLOAD_LIMITS is what bounds that today.
"""

import hashlib
import io
import json
import logging
import os

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

#: What B queried: an ordinary binary, stored under the digest of these bytes.
VICTIM_BINARY = b"MZ this is the payload a contributor queried\x00" * 4
VICTIM_SHA256 = hashlib.sha256(VICTIM_BINARY).hexdigest()


def smda_report(sha256, family="attacker.family"):
    """The smallest dict `SmdaReport.fromDict` accepts. `sha256` is a plain field of
    the report - smda writes the digest of the file it disassembled there, and nothing
    downstream of an upload recomputes it."""
    return {
        "architecture": "intel", "base_addr": 4194304, "binary_size": 64, "bitness": 64,
        "code_areas": [], "code_sections": [], "confidence_threshold": 0.5,
        "disassembly_errors": {}, "execution_time": 0.1, "identified_alignment": 16,
        "metadata": {
            "family": family, "filename": "report.exe", "version": "1.0",
            "component": "", "is_library": False,
        },
        "message": "", "oep": 4194304, "sha256": sha256, "smda_version": "4.4.4",
        "statistics": {}, "status": "ok", "timestamp": "2026-08-07T12-00-00", "xcfg": {},
    }


def uploads_dir(app):
    return os.path.join(app.instance_path, "temp", "uploads")


def stored(app):
    """name -> bytes, for everything the route has kept so far."""
    directory = uploads_dir(app)
    return {name: open(os.path.join(directory, name), "rb").read()
            for name in sorted(os.listdir(directory))}


def query_binary(client, content, filename="sample.exe"):
    """The 'unmapped' branch: a plain file, hashed by the view itself."""
    return client.post(
        "/analyze/query",
        data={"options": "unmapped", "file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
    )


def query_smda(client, report, filename="report.smda"):
    """The '.smda' branch. The form reveals base_addr for a report, and the view
    parses it as hex before it ever looks at the file."""
    body = json.dumps(report).encode()
    return client.post(
        "/analyze/query",
        data={
            "options": "smda", "base_addr": "0x400000",
            "file": (io.BytesIO(body), filename),
        },
        content_type="multipart/form-data",
    )


def test_a_visitor_smda_upload_cannot_destroy_another_users_stored_query(app, client, as_role):
    """The bug, end to end. A contributor queries a binary; the file kept for it is
    named after the bytes. A visitor then uploads a report *declaring* that same
    digest. With the name taken from the declared field the second write lands on the
    first file - mode "wb", no existence check - and the stored query is gone for
    good, because nothing ever puts it back."""
    as_role("contributor", username="victim")
    assert query_binary(client, VICTIM_BINARY).status_code == 202
    assert stored(app)[VICTIM_SHA256] == VICTIM_BINARY, "the query was never stored"

    as_role("visitor", username="attacker")
    assert query_smda(client, smda_report(VICTIM_SHA256)).status_code == 202

    assert stored(app)[VICTIM_SHA256] == VICTIM_BINARY, \
        "a visitor's upload overwrote another user's stored query"


def test_an_smda_upload_is_named_by_the_bytes_that_were_uploaded(app, client, as_role):
    """The rule the other two branches already follow, stated directly: the name is a
    digest of the request body, so it cannot be chosen without producing the bytes."""
    as_role("visitor")
    report = smda_report("00" * 32)
    body = json.dumps(report).encode()
    assert query_smda(client, report).status_code == 202

    assert stored(app) == {hashlib.sha256(body).hexdigest(): body}


def test_a_declared_digest_no_longer_names_a_file(app, client, as_role):
    """The attacker's half of the same statement: nothing appears at the name the
    uploader asked for, so no amount of guessing hashes reserves a path."""
    as_role("visitor")
    assert query_smda(client, smda_report(VICTIM_SHA256)).status_code == 202

    assert VICTIM_SHA256 not in stored(app)


def test_the_same_bytes_from_two_users_collide_on_one_file_that_still_holds_them(app, client, as_role):
    """Naming by content leaves exactly one collision: two people uploading the same
    file. Both writes then go to the same path - so this checks what that costs.

    The name is a function of the content, so the second write is byte-identical to
    the first: the file after it is what it was before, and the second uploader's own
    query is intact too, since it *is* the same query. That is why the fix needs no
    existence check to go with it - there is nothing to protect. What collides is
    storage, which is the deduplication the other two branches have always had."""
    as_role("visitor", username="first")
    assert query_smda(client, smda_report("11" * 32)).status_code == 202
    after_first = stored(app)
    assert len(after_first) == 1

    as_role("visitor", username="second")
    assert query_smda(client, smda_report("11" * 32)).status_code == 202

    assert stored(app) == after_first, "the same bytes stored twice are not the same bytes"
