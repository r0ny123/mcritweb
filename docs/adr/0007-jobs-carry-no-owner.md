# Jobs carry no owner, so MCRITweb cannot annotate activity with one

---
status: accepted — blocked upstream, and there is a design question to settle first
---

Issue #37 proposes annotating objects such as jobs with user uuids, for accountability,
convenience and personalization. **MCRITweb cannot do this**, because the storage that
would hold the annotation is the backend's job document and this application has no write
path into it.

What already flows: MCRITweb sends a username on every backend call —
`views/client.py::default_client_factory` passes `username=get_username()` into
`McritClient`, which puts it in `self.headers`. The backend uses it for **logging only**:
`mcrit/server/utils.py:10-13` reads the header and calls
`index._storage.dbLogEvent(message, username=username)` → `MongoDbStorage._dbLog`, which
writes to a `logs` collection with a `username` index. The only *domain object* that
persists a username is `FunctionLabelEntry`.

Jobs carry no owner field at all. `mcrit/queue/LocalQueue.py::Job` exposes `locked_by`
(the worker), `created_at`, `payload` and `all_dependencies` — nothing about who asked.
The captured job fixtures confirm it: `cross_compare.job.json` has no user key of any
kind.

MCRITweb also has no user uuid to send. `sql/create_table_user.sql` is `id INTEGER
PRIMARY KEY AUTOINCREMENT, username, password, role, registered, last_login, apitoken`.
The only uuids in the codebase are `server_uuid` (per-instance, `authentication.py:92`)
and the md5-of-uuid4 used to mint `apitoken`.

## Consequences

**Do not add a `uuid` column to the user table in anticipation.** It would be dead schema:
per `AGENTS.md` a column change means touching `sql/`, `db.py`, `db.migrate()` and the
README version history — four files, one of them among the most contended in the repo —
for no user-visible effect, and `db.py` would then carry a field nothing reads.

There is a design question that should be settled **before** any of this, and it decides
whether MCRITweb needs a schema change at all: **`username` is already on the wire.** If
usernames cannot be renamed or reused in a deployment, `username` gets accountability with
zero change on this side. A uuid is only better if they can. The issue should ask that
question rather than assume the uuid.

## Outcome

Re-file the substance on `danielplohmann/mcrit` as a request for an owner field on the
job document, and put the username-versus-uuid question to the maintainers there, since
the answer determines what MCRITweb has to send.
