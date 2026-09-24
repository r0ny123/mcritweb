"""The /jobs selectors (danielplohmann/mcrit PR #214) on a live server, against a Python filter
of the whole method; job_ids against single GETs; the 400 and the empty selector; timing; the
query plan. Needs a server running that branch. Read-only.
usage: selector_live.py [jobs url, default http://127.0.0.1:8110/jobs/]"""
import json, statistics, sys, time, requests, pymongo
from bson.regex import Regex
B = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8110/jobs/"
def jobs(**params):
    r = requests.get(B, params=params); r.raise_for_status(); return r.json()["data"]
def first_arg(job):
    return json.loads(job["payload"]["params"]).get("0")
ok = True
for method in ("getMatchesForSample", "getMatchesForSampleVs"):
    whole = jobs(method=method)
    for ids in (list(range(1, 26)), list(range(0, 25)), [16, 17], list(range(24, 61, 4)), [1], [-1, 1, 10], list(range(0, 66))):
        got = jobs(method=method, sample_ids=",".join(map(str, ids)))
        want = [j for j in whole if first_arg(j) in ids]
        same = got == want
        ok &= same
        print(f"{method:22} {len(ids):2} ids from {ids[0]}: {len(got):3} jobs, equal to the python check: {same}")
for job in jobs(method="combineMatchesToCross")[:3]:
    first = json.loads(job["payload"]["params"]).get("0")
    deps = [d for d in (first.values() if isinstance(first, dict) else []) if isinstance(d, str)]
    got = jobs(job_ids=",".join(deps))
    same = sorted(j["_id"]["$oid"] for j in got) == sorted(deps) and all(j == requests.get(B + j["_id"]["$oid"]).json()["data"] for j in got)
    ok &= same
    print(f"cross compare {job['_id']['$oid'][:8]}: {len(deps)} dependencies, job_ids equal to single GETs: {same}")
print("400 without method:", requests.get(B, params={"sample_ids": "1"}).status_code, "| sample_ids=x,y:", len(jobs(method="getMatchesForSample", sample_ids="x,y")), "jobs")
def med(**params):
    t = []
    for _ in range(7):
        s = time.perf_counter(); r = requests.get(B, params=params); t.append(time.perf_counter() - s)
    return statistics.median(t) * 1000, len(r.content)
for label, params in (("whole method", {"method": "getMatchesForSample"}), ("25 samples (0-24)", {"method": "getMatchesForSample", "sample_ids": ",".join(map(str, range(25)))}), ("2 samples", {"method": "getMatchesForSample", "sample_ids": "16,17"})):
    ms, size = med(**params); print(f"  {label}: median {ms:.1f} ms, {size:,} bytes")
coll = pymongo.MongoClient("127.0.0.1", 27017)["mcrit"]["queue"]
q = {"payload.descriptor": {"$in": [Regex('^\\["getMatchesForSample", \\{"0": %d%s' % (i, e)) for i in range(25) for e in (",", "\\}")]}}
ex = coll.find(q, sort=[("_id", -1)]).explain()
def st(n, out):
    out.append(n["stage"] + (":" + n["indexName"] if "indexName" in n else ""))
    for c in ([n["inputStage"]] if "inputStage" in n else []) + n.get("inputStages", []): st(c, out)
    return out
print("live plan, 25 samples:", " <- ".join(st(ex["queryPlanner"]["winningPlan"], [])), "| keys", ex["executionStats"]["totalKeysExamined"], "docs", ex["executionStats"]["totalDocsExamined"], "returned", ex["executionStats"]["nReturned"])
print("ALL OK" if ok else "MISMATCH")
