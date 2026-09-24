"""Create a MCRITweb instance folder for a checkout: the database schema, the server entry
pointing at the local mcrit, and the test login.

usage: make_instance.py <mcritweb checkout> [mcrit url]

The schema comes from the checkout's own mcritweb/sql files, the ones `flask init-db` runs,
before the app is created: create_app migrates the database it finds on startup. Running it
again on an existing instance only makes sure the test user and the server entry exist.
"""

import glob
import os
import sqlite3
import sys
import uuid

USERNAME, PASSWORD = "analyst1", "Passw0rd-live!"

checkout = os.path.abspath(sys.argv[1])
mcrit_url = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
instance = os.path.join(checkout, "instance")
database = os.path.join(instance, "mcritweb.sqlite")
os.makedirs(instance, exist_ok=True)

if not os.path.exists(database):
    connection = sqlite3.connect(database)
    for script in sorted(glob.glob(os.path.join(checkout, "mcritweb", "sql", "create_table_*.sql"))):
        with open(script, encoding="utf-8") as handle:
            connection.executescript(handle.read())
    connection.commit()
    connection.close()

sys.path.insert(0, checkout)
from werkzeug.security import generate_password_hash  # noqa: E402

from mcritweb import create_app  # noqa: E402
from mcritweb.db import ServerInfo, UserInfo, generate_apitoken  # noqa: E402

app = create_app(instance_path=instance)
with app.app_context():
    server = ServerInfo.fromDb()
    if server is None or not server.url:
        server = server or ServerInfo()
        server.url = mcrit_url
        server.operation_mode = "multi"
        server.registration_token = ""
        server.server_token = ""
        server.server_uuid = str(uuid.uuid4())
        server.server_version = ""
        server.saveToDb()
    if UserInfo.fromDb(username=USERNAME) is None:
        user = UserInfo()
        user.username = USERNAME
        user.password = generate_password_hash(PASSWORD)
        user.role = "admin"
        user.apitoken = generate_apitoken()
        user.saveToDb(withPassword=True)
    print(f"instance {instance}: server {ServerInfo.fromDb().url}, login {USERNAME} / {PASSWORD} (admin)")
