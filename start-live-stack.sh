#!/bin/bash
# Start the live stack set up by setup-live-stack.sh: MongoDB on 27017, the mcrit server on 8000
# with one worker, and MCRITweb from the given checkout on 5000.
#
# usage: start-live-stack.sh <mcritweb checkout>
# env:   LIVE        as for setup-live-stack.sh (default ~/live-stack)
#        PYTHONPATH  a mcrit checkout to use instead of the installed release, for MCRITweb and
#                    the server alike (e.g. a branch with new client methods)
set -euo pipefail
MCRITWEB=$(cd "${1:?usage: start-live-stack.sh <mcritweb checkout>}" && pwd)
LIVE=${LIVE:-$HOME/live-stack}
V=$LIVE/venv/bin
mkdir -p "$LIVE/logs" "$LIVE/pids"

wait_for() {  # wait_for <what> <url>
    for _ in $(seq 1 60); do curl -s -m 2 -o /dev/null "$2" && return 0; sleep 1; done
    echo "timed out waiting for $1 ($2)" >&2; return 1
}
start() {  # start <name> <dir> <command...>: run detached in a session of its own, keep its pid
    local name=$1 dir=$2; shift 2
    # the process writes its own pid: setsid forks when it has to, and $! would be the parent.
    # The subshell's own output goes to the log too, so nothing keeps the caller's stdout open.
    ( cd "$dir" && exec setsid sh -c 'echo $$ > "$0"; exec "$@"' "$LIVE/pids/$name.pid" "$@" ) >> "$LIVE/logs/$name.log" 2>&1 < /dev/null &
}

case "$(cat "$LIVE/mongo-mode")" in
    docker)
        docker info >/dev/null 2>&1 || { ( exec setsid dockerd ) >> "$LIVE/logs/dockerd.log" 2>&1 < /dev/null & for _ in $(seq 1 60); do docker info >/dev/null 2>&1 && break; sleep 1; done; }
        docker start mcrit-mongo >/dev/null ;;
    local)
        mongod --dbpath "$LIVE/db" --port 27017 --bind_ip 127.0.0.1 --fork --logpath "$LIVE/logs/mongod.log" >/dev/null 2>&1 || true ;;
esac
for _ in $(seq 1 60); do python3 -c "import socket; socket.create_connection(('127.0.0.1', 27017), 1)" 2>/dev/null && break; sleep 1; done

start mcrit-server "$LIVE" "$V/mcrit" server --gunicorn
start mcrit-worker "$LIVE" "$V/mcrit" worker
wait_for "the mcrit server" http://127.0.0.1:8000/status
start mcritweb "$MCRITWEB" env FLASK_APP=mcritweb FLASK_DEBUG=1 "$V/flask" run --port 5000 --no-reload
wait_for MCRITweb http://127.0.0.1:5000/login

echo "MongoDB 127.0.0.1:27017, mcrit http://127.0.0.1:8000, MCRITweb http://127.0.0.1:5000 ($MCRITWEB)"
echo "login analyst1 / Passw0rd-live!; logs in $LIVE/logs; stop with stop-live-stack.sh"
