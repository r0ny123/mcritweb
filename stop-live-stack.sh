#!/bin/bash
# Stop what start-live-stack.sh and tools/lw.sh started, by the pids they recorded, then MongoDB.
# The data stays in $LIVE/db; start-live-stack.sh brings it all back.
LIVE=${LIVE:-$HOME/live-stack}
for pidfile in "$LIVE"/pids/*.pid; do
    [ -e "$pidfile" ] || continue
    pid=$(cat "$pidfile")
    # setsid made each one a session leader: stop the whole session (gunicorn's workers too)
    kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null
    rm -f "$pidfile"
done
case "$(cat "$LIVE/mongo-mode" 2>/dev/null)" in
    docker) docker stop mcrit-mongo >/dev/null 2>&1 ;;
    local) mongod --dbpath "$LIVE/db" --shutdown >/dev/null 2>&1 ;;
esac
echo "stopped"
