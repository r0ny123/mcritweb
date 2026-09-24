#!/bin/bash
# One-time setup of the live stack on a fresh machine:
#   - MongoDB 8.0 with the corpus from data/mcrit-db.archive.gz restored into it;
#   - a Python venv with mcrit (1.9.0 by default), gunicorn and MCRITweb's requirements;
#   - a MCRITweb instance folder in the given checkout, pointing at the local mcrit.
#
# usage: setup-live-stack.sh <mcritweb checkout>
# env:   LIVE           where the stack keeps its data, logs and venv (default ~/live-stack)
#        MCRIT_VERSION  the mcrit release to install (default 1.9.0)
#
# MongoDB: a mongod and mongorestore already on PATH are used as they are. Otherwise the official
# mongo:8.0 image runs through Docker, with host networking: fastdl.mongodb.org is refused by some
# environments' network policy, while Docker Hub is usually reachable.
# Afterwards, start everything with start-live-stack.sh.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MCRITWEB=$(cd "${1:?usage: setup-live-stack.sh <mcritweb checkout>}" && pwd)
LIVE=${LIVE:-$HOME/live-stack}
MCRIT_VERSION=${MCRIT_VERSION:-1.9.0}
mkdir -p "$LIVE/db" "$LIVE/logs" "$LIVE/pids"

wait_for() {  # wait_for <what> <command...>
    local what=$1; shift
    for _ in $(seq 1 60); do "$@" >/dev/null 2>&1 && return 0; sleep 1; done
    echo "timed out waiting for $what" >&2; return 1
}

echo "== MongoDB"
if command -v mongod >/dev/null && command -v mongorestore >/dev/null; then
    echo local > "$LIVE/mongo-mode"
    mongod --dbpath "$LIVE/db" --port 27017 --bind_ip 127.0.0.1 --fork --logpath "$LIVE/logs/mongod.log" >/dev/null
    restore() { mongorestore --quiet --archive="$HERE/data/mcrit-db.archive.gz" --gzip --drop; }
else
    command -v docker >/dev/null || { echo "neither mongod on PATH nor docker" >&2; exit 1; }
    echo docker > "$LIVE/mongo-mode"
    if ! docker info >/dev/null 2>&1; then
        ( exec setsid dockerd ) > "$LIVE/logs/dockerd.log" 2>&1 < /dev/null &
        wait_for dockerd docker info
    fi
    docker pull -q mongo:8.0 >/dev/null
    docker rm -f mcrit-mongo >/dev/null 2>&1 || true
    docker run -d --name mcrit-mongo --network host -v "$LIVE/db:/data/db" mongo:8.0 --bind_ip 127.0.0.1 --port 27017 >/dev/null
    restore() { docker exec -i mcrit-mongo mongorestore --quiet --archive --gzip --drop < "$HERE/data/mcrit-db.archive.gz"; }
fi
wait_for "MongoDB on 27017" python3 -c "import socket; socket.create_connection(('127.0.0.1', 27017), 1)"
restore
echo "restored data/mcrit-db.archive.gz ($(cat "$LIVE/mongo-mode") MongoDB)"

echo "== Python venv ($LIVE/venv)"
[ -x "$LIVE/venv/bin/python" ] || python3 -m venv "$LIVE/venv"
"$LIVE/venv/bin/pip" install -q --upgrade pip
"$LIVE/venv/bin/pip" install -q "mcrit==$MCRIT_VERSION" gunicorn requests -r "$MCRITWEB/requirements.txt"
"$LIVE/venv/bin/python" -c "from importlib.metadata import version; print('mcrit', version('mcrit'), '| flask', version('flask'), '| smda', version('smda'))"

echo "== The corpus"
"$LIVE/venv/bin/python" "$HERE/tools/check_corpus.py"

echo "== MCRITweb instance"
"$LIVE/venv/bin/python" "$HERE/make_instance.py" "$MCRITWEB" http://127.0.0.1:8000
echo "$MCRITWEB/instance" > "$LIVE/reference-instance"

echo
echo "Set up. Start the stack with: $HERE/start-live-stack.sh $MCRITWEB"
