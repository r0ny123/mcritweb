"""Per page: backend calls per view (from the counting proxies), time (median of 3 warm
loads), and whether the HTML equals the base instance's.
usage: live_follow.py <branch port> <branch proxy> <path>...
The base is BASE_PORT behind BASE_PROXY (default 5001 behind 7811); start both with lw.sh.
The proxies' logs are in $LIVE/logs (default ~/live-stack)."""
import os, re, statistics, sys, time
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import web

LOGS = os.path.join(os.environ.get("LIVE", os.path.expanduser("~/live-stack")), "logs")
NOISE = [
    (re.compile(r'(name="csrf-token" content=")[^"]+'), r"\1X"),
    (re.compile(r'(name="csrf_token" value=")[^"]+'), r"\1X"),
    (re.compile(r'nonce="[^"]+"'), 'nonce="X"'),
    (re.compile(r'("X-CSRF-?Token":\s*")[0-9a-f]+', re.I), r"\1X"),
    (re.compile(r"\b\d+\.\d+ ?(?:ms|s)\b"), "T"),
    (re.compile(r"[?&]v=[0-9a-f]{6,}"), "?v=X"),
    (re.compile(r"127\.0\.0\.1:\d+"), "HOST"),
]

def normalize(text):
    for pattern, repl in NOISE:
        text = pattern.sub(repl, text)
    return [line.rstrip() for line in text.splitlines() if line.strip()]

def calls(proxy):
    return open(f"{LOGS}/count_{proxy}.log").read().splitlines()

def measure(session, proxy, path):
    session.get(session.base + path)  # warm the result cache
    before = len(calls(proxy))
    response = session.get(session.base + path, allow_redirects=False)
    made = calls(proxy)[before:]
    times = []
    for _ in range(3):
        started = time.perf_counter(); session.get(session.base + path); times.append(time.perf_counter() - started)
    return response, made, statistics.median(times)

branch_port, branch_proxy, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
BASE_PORT, BASE_PROXY = os.environ.get("BASE_PORT", "5001"), os.environ.get("BASE_PROXY", "7811")
master, branch = web.login(f"http://127.0.0.1:{BASE_PORT}"), web.login(f"http://127.0.0.1:{branch_port}")
for path in paths:
    rm, cm, tm = measure(master, BASE_PROXY, path)
    rb, cb, tb = measure(branch, branch_proxy, path)
    same = rm.status_code == rb.status_code and normalize(rm.text) == normalize(rb.text)
    kinds = lambda made: dict(Counter(re.sub(r"[?/].*", "", line.split(" ", 1)[1].lstrip("/")) if " " in line else line for line in made))
    print(f"{path}\n   base:   {len(cm)} calls {kinds(cm)}, {tm*1000:.0f} ms\n   branch: {len(cb)} calls {kinds(cb)}, {tb*1000:.0f} ms\n   html same as the base: {same}")
