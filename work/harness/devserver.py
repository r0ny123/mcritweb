"""Boot MCRITweb against the captured corpus in tests/fixtures/ and serve it.

There is no MongoDB and no docker daemon in this environment, so a real mcrit
backend cannot be brought up (see work/SETUP.md). The project already ships an
offline stand-in for exactly this - `CorpusMcritClient` in tests/fixtureData.py,
which serves real captured reports - and the app factory exposes the seam it
plugs into (`MCRIT_CLIENT_FACTORY`). This wires the two together behind a normal
HTTP server so pages can be walked with curl instead of only through
`app.test_client()`.

Usage:
    python work/harness/devserver.py [--port 5001] [--role admin]

Then:  curl -s -b work/harness/cookies.txt http://127.0.0.1:5001/explore/samples
The session cookie for the seeded user is written to --cookie-file on startup.
"""

import argparse
import os
import pathlib
import shutil
import sys
import tempfile

# The repository this harness drives. Defaults to the checkout it lives in, but a
# fix branch does not carry work/ - so a copy kept outside the tree can point at the
# checkout with MCRITWEB_REPO and keep working across branch switches.
REPO = pathlib.Path(os.environ.get("MCRITWEB_REPO") or pathlib.Path(__file__).resolve().parents[2]).resolve()
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from werkzeug.security import generate_password_hash  # noqa: E402

from mcritweb import create_app  # noqa: E402
from mcritweb.db import ServerInfo, UserInfo, init_db  # noqa: E402


def build(instance_path, role):
    from fixtureData import CorpusMcritClient

    backend = CorpusMcritClient()
    app = create_app(
        {
            "DATABASE": os.path.join(instance_path, "mcritweb.sqlite"),
            "SECRET_KEY": "harness-secret",
            "SESSION_COOKIE_SECURE": False,
            "MCRIT_CLIENT_FACTORY": lambda **kwargs: backend,
            "MCRIT_SERVER_PROBE": lambda: True,
        },
        instance_path=instance_path,
    )
    with app.app_context():
        init_db()
        server_info = ServerInfo()
        server_info.url = "http://127.0.0.1:8000"
        server_info.operation_mode = "multi"
        server_info.registration_token = ""
        server_info.server_token = ""
        server_info.server_uuid = "harness-uuid"
        server_info.server_version = "harness"
        server_info.saveToDb()

        user = UserInfo()
        user.username = role + "user"
        user.password = generate_password_hash("password")
        user.role = role
        user.apitoken = "apitoken-" + role
        user.saveToDb()
        user_id = UserInfo.fromDb(username=role + "user").user_id
    return app, backend, user_id


def write_cookie(app, user_id, cookie_file, port):
    """A Netscape cookie jar holding a signed session for the seeded user."""
    from flask.sessions import SecureCookieSessionInterface

    serializer = SecureCookieSessionInterface().get_signing_serializer(app)
    value = serializer.dumps({"user_id": user_id})
    pathlib.Path(cookie_file).write_text(
        "# Netscape HTTP Cookie File\n"
        f"127.0.0.1\tFALSE\t/\tFALSE\t0\tsession\t{value}\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--role", default="admin")
    parser.add_argument("--instance", default=None, help="reuse an instance dir instead of a fresh temp one")
    parser.add_argument("--cookie-file", default=str(pathlib.Path(__file__).parent / "cookies.txt"))
    args = parser.parse_args()

    instance_path = args.instance or tempfile.mkdtemp(prefix="mcritweb-harness-")
    if args.instance is None:
        os.makedirs(instance_path, exist_ok=True)
    app, _backend, user_id = build(instance_path, args.role)
    write_cookie(app, user_id, args.cookie_file, args.port)
    print(f"instance={instance_path} role={args.role} user_id={user_id} cookies={args.cookie_file}", flush=True)
    try:
        app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False, threaded=True)
    finally:
        if args.instance is None:
            shutil.rmtree(instance_path, ignore_errors=True)


if __name__ == "__main__":
    main()
