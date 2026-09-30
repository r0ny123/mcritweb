#!/bin/bash
# One-time setup of the live stack on a fresh machine:
#   - MongoDB 8.0 with the corpus from data/mcrit-db.archive.gz restored into it;
#   - a Python venv with mcrit (1.13.0 by default), gunicorn and MCRITweb's requirements, as
#     $LIVE/venv-<version> with $LIVE/venv linking to it;
#   - a MCRITweb instance folder in the given checkout, pointing at the local mcrit.
#
# usage: setup-live-stack.sh <mcritweb checkout>
# env:   LIVE           where the stack keeps its data, logs and venv (default ~/live-stack)
#        MCRIT_VERSION  the mcrit release to install (default 1.13.0). It comes from PyPI, or from
#                       its tag in danielplohmann/mcrit while PyPI doesn't have it yet
#        PYTHON         the interpreter for the venv (default python3.12: mcrit declares
#                       requires-python >=3.12 since 1.10.0)
#
# Every version gets a venv of its own, and $LIVE/venv links to the last one set up, which is what
# start-live-stack.sh runs. Going back is `ln -sfn venv-<version> $LIVE/venv` and a restart; a
# venv from before this layout, a directory at $LIVE/venv, is moved to venv-<its mcrit version>.
#
# MongoDB: a mongod and mongorestore already on PATH are used as they are. Otherwise the official
# mongo:8.0 image runs through Docker, with host networking: fastdl.mongodb.org is refused by some
# environments' network policy, while Docker Hub is usually reachable.
# Afterwards, start everything with start-live-stack.sh.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MCRITWEB=$(cd "${1:?usage: setup-live-stack.sh <mcritweb checkout>}" && pwd)
LIVE=${LIVE:-$HOME/live-stack}
MCRIT_VERSION=${MCRIT_VERSION:-1.13.0}
PYTHON=${PYTHON:-python3.12}
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

VENV=$LIVE/venv-$MCRIT_VERSION
echo "== Python venv ($VENV)"
if [ -d "$LIVE/venv" ] && [ ! -L "$LIVE/venv" ]; then
    # the old layout. Its scripts name $LIVE/venv in their shebangs, and keep working while the
    # link points back at it
    old=$("$LIVE/venv/bin/python" -c "from importlib.metadata import version; print(version('mcrit'))" 2>/dev/null || echo unknown)
    [ -e "$LIVE/venv-$old" ] && { echo "$LIVE/venv is a directory and $LIVE/venv-$old exists; move one of them" >&2; exit 1; }
    mv "$LIVE/venv" "$LIVE/venv-$old"
    echo "moved the existing venv (mcrit $old) to $LIVE/venv-$old"
fi
command -v "$PYTHON" >/dev/null || { echo "$PYTHON not found; set PYTHON to an interpreter mcrit $MCRIT_VERSION supports" >&2; exit 1; }
[ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"
"$VENV/bin/pip" install -q --upgrade pip
if ! "$VENV/bin/pip" install -q "mcrit==$MCRIT_VERSION" gunicorn requests -r "$MCRITWEB/requirements.txt" 2>/dev/null; then
    echo "mcrit $MCRIT_VERSION is not on PyPI (yet); installing its tag from danielplohmann/mcrit"
    "$VENV/bin/pip" install -q "mcrit @ git+https://github.com/danielplohmann/mcrit@v$MCRIT_VERSION" gunicorn requests -r "$MCRITWEB/requirements.txt"
fi
ln -sfn "venv-$MCRIT_VERSION" "$LIVE/venv"
"$LIVE/venv/bin/python" -c "import sys; from importlib.metadata import version; print('python', sys.version.split()[0], '| mcrit', version('mcrit'), '| flask', version('flask'), '| smda', version('smda'))"

echo "== The corpus"
"$LIVE/venv/bin/python" "$HERE/tools/check_corpus.py"

echo "== MCRITweb instance"
"$LIVE/venv/bin/python" "$HERE/make_instance.py" "$MCRITWEB" http://127.0.0.1:8000
echo "$MCRITWEB/instance" > "$LIVE/reference-instance"

echo
echo "Set up. Start the stack with: $HERE/start-live-stack.sh $MCRITWEB"
