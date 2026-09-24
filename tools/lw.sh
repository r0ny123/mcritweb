#!/bin/bash
# Run MCRITweb from any checkout on <port>, talking to mcrit on <backend port> through a
# request-counting proxy on <proxy port>, which logs one line per backend request to
# $LIVE/logs/count_<proxy port>.log (what live_follow.py counts). The checkout gets a copy of
# the reference instance (the test login) the first time. Stop it with stop-live-stack.sh.
#
# usage: lw.sh <mcritweb checkout> <port> <proxy port> [backend port, default 8000] [mcrit checkout]
#   a mcrit checkout given last is put on PYTHONPATH, e.g. a branch with new client methods
set -euo pipefail
LIVE=${LIVE:-$HOME/live-stack}
HERE=$(cd "$(dirname "$0")" && pwd)
V=$LIVE/venv/bin
WT=$(cd "$1" && pwd); PORT=$2; PROXY=$3; BACKEND=${4:-8000}; MC=${5:-}
mkdir -p "$LIVE/logs" "$LIVE/pids"
[ -d "$WT/instance" ] || cp -a "$(cat "$LIVE/reference-instance")" "$WT/instance"
"$V/python" -c "
import sqlite3; c = sqlite3.connect('$WT/instance/mcritweb.sqlite'); c.execute(\"UPDATE server SET url='http://127.0.0.1:$PROXY'\"); c.commit()"
for name in "proxy-$PROXY" "web-$PORT"; do  # a previous run on these ports
    [ -e "$LIVE/pids/$name.pid" ] && { kill -- "-$(cat "$LIVE/pids/$name.pid")" 2>/dev/null || true; rm -f "$LIVE/pids/$name.pid"; }
done
sleep 0.5
: > "$LIVE/logs/count_$PROXY.log"
# each writes its own pid, and its subshell's output goes to a file, so the caller's stdout is free
( exec setsid sh -c 'echo $$ > "$0"; exec "$@"' "$LIVE/pids/proxy-$PROXY.pid" "$V/python" "$HERE/countproxy.py" "$PROXY" 127.0.0.1 "$BACKEND" "$LIVE/logs/count_$PROXY.log" ) > /dev/null 2>&1 < /dev/null &
( cd "$WT" && exec env FLASK_APP=mcritweb FLASK_DEBUG=1 PYTHONPATH="$MC" setsid sh -c 'echo $$ > "$0"; exec "$@"' "$LIVE/pids/web-$PORT.pid" "$V/flask" run --port "$PORT" --no-reload ) > "$LIVE/logs/web_$PORT.log" 2>&1 < /dev/null &
for _ in $(seq 1 40); do curl -s -m 2 -o /dev/null "http://127.0.0.1:$PORT/login" && break; sleep 0.5; done
echo "$WT on $PORT -> proxy $PROXY -> $BACKEND${MC:+ (mcrit from $MC)}"
