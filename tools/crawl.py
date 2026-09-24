"""usage: crawl.py urls   - build urls.json from the live backend
          crawl.py <base> <tag> - GET every url as analyst1, write crawl_<tag>.json {url: [status, seconds, error-title]}"""
import json, re, sys, time
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
L = os.path.join(os.environ.get("LIVE", os.path.expanduser("~/live-stack")), "crawl")
os.makedirs(L, exist_ok=True)

if sys.argv[1] == "urls":
    import requests
    from mcrit.client.McritClient import McritClient
    c = McritClient(mcrit_server="http://127.0.0.1:8000")
    samples = c.getSamples(start=0, limit=200)
    samples = list(samples.values()) if isinstance(samples, dict) else samples
    sample_ids = sorted(s.sample_id for s in samples)
    family_ids = sorted({s.family_id for s in samples})
    functions = c.getFunctionsBySampleId(8) or []
    function_ids = sorted((f.function_id for f in (functions.values() if isinstance(functions, dict) else functions)))[:3]
    jobs = requests.get("http://127.0.0.1:8000/jobs?limit=500").json()["data"]
    job_ids = [j["_id"]["$oid"] if isinstance(j["_id"], dict) else j["_id"] for j in jobs]
    methods = sorted({j["payload"]["method"] for j in jobs if isinstance(j.get("payload"), dict) and j["payload"].get("method")})
    urls = ["/", "/explore/samples", "/explore/families", "/explore/functions", "/explore/search?query=launcher", "/explore/search?query=8",
            "/explore/samples?query=distlib", "/explore/functions?query=1", "/explore/statistics", "/explore/familyNames",
            "/analyze/compare", "/analyze/compare_versus", "/analyze/query", "/analyze/unique_blocks", "/analyze/cross_compare_from_hash_list",
            f"/analyze/cross_compare?samples={sample_ids[8]},{sample_ids[9]},{sample_ids[12]}", f"/analyze/compare/{sample_ids[8]}",
            f"/analyze/compare/{sample_ids[8]}/{sample_ids[12]}", f"/analyze/blocks/sample/{sample_ids[16]}", f"/analyze/blocks/family/{family_ids[1]}",
            "/data/jobs", "/data/export", "/data/import", "/data/submit", "/admin/server", "/admin/users/", "/admin/change_column_settings",
            "/admin/change_password", "/admin/change_username", "/settings", "/help"]
    urls += [f"/data/jobs?active={m}" for m in methods]
    urls += [f"/explore/samples/{i}" for i in sample_ids] + [f"/explore/families/{i}" for i in family_ids]
    for fid in function_ids:
        urls += [f"/explore/functions/{fid}", f"/explore/fetchDotGraph/{fid}", f"/analyze/compare_function/{fid}"]
    if len(function_ids) > 1:
        a, b = function_ids[:2]
        urls += [f"/explore/fetchCombinedDotGraph/{a}/{b}", f"/data/matches/function/{a}/{b}"]
    for jid in job_ids:
        urls += [f"/data/jobs/{jid}", f"/data/result/{jid}", f"/data/result/{jid}/download", f"/data/linkhunt/{jid}"]
    json.dump(urls, open(f"{L}/urls.json", "w"), indent=0)
    print(len(urls), "urls;", len(job_ids), "jobs;", len(sample_ids), "samples")
else:
    import web
    base, tag = sys.argv[1], sys.argv[2]
    s = web.login(base)
    out = {}
    for url in json.load(open(f"{L}/urls.json")):
        t = time.time()
        try:
            r = s.get(base + url, allow_redirects=False, timeout=120)
            title = re.search(r"<title>(.*?)</title>", r.text, re.S)
            err = title.group(1).strip()[:160] if r.status_code >= 500 and title else ""
            out[url] = [r.status_code, round(time.time() - t, 2), err]
        except Exception as e:
            out[url] = [-1, round(time.time() - t, 2), repr(e)[:160]]
    json.dump(out, open(f"{L}/crawl_{tag}.json", "w"), indent=0)
    bad = {u: v for u, v in out.items() if v[0] >= 500 or v[0] < 0}
    print(tag, len(out), "urls;", sum(1 for v in out.values() if v[0] == 200), "x200;", len(bad), "x5xx")
    for u, v in bad.items():
        print("  5xx", u, v)
