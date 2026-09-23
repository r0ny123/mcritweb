#!/usr/bin/env python3
"""File the mcrit issues, open the mcrit PRs and the MCRITweb follow-ups, and point the
familiary/mcritweb PRs and issues at them.

Run the steps in order, each first without --apply (it prints what it would do and changes
nothing), then with --apply. Every step skips what is already done, so a step can be re-run.

    python3 finish-upstream.py search              duplicate candidates on danielplohmann/mcrit
    python3 finish-upstream.py issues [--apply]    file the three new mcrit issues, find the batch one
    python3 finish-upstream.py prs [--apply]       open the four mcrit PRs from r0ny123/mcrit
    python3 finish-upstream.py followups [--apply] push the three MCRITweb follow-ups to familiary, open their PRs
    python3 finish-upstream.py bodies [--apply]    point four familiary PR descriptions at them
    python3 finish-upstream.py comments [--apply]  post the familiary issue comments
    python3 finish-upstream.py verify              check all of it, and print CI

Issue and PR numbers are kept in finish-state.json in the current directory. `--set key=N`
records one by hand, e.g. `--set batch=210` (keys: rename, edits, selector, batch for the
issues; rename_pr, edits_pr, batch_pr, selector_pr for the PRs; f191, f192, f202 for the
follow-up PRs on familiary).

Run it from the pr-text directory of r0ny123/mcritweb's `claude/admiring-turing-4ihzfx`
branch. Needs `gh`, logged in as r0ny123, and `git`.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = "finish-state.json"
ME = "r0ny123"
MCRIT = "danielplohmann/mcrit"
FAM = "familiary/mcritweb"
FORK = "https://github.com/r0ny123/mcrit"
FORK_WEB = "https://github.com/r0ny123/mcritweb"

#: the new mcrit issues, filed in this order: the edits issue names the rename issue
ISSUES = [
    ("rename", "issue-mcrit-family-rename-same-name.md"),
    ("edits", "issue-mcrit-edit-length-checks.md"),
    ("selector", "issue-mcrit-queue-sample-selector.md"),
]
#: filed by hand already; found by its title
BATCH_TITLE = "Expose a batch sample lookup"

#: the mcrit PRs, opened in this order: the edits PR names the rename PR
PRS = [
    ("rename", "fix/family-rename-same-name", "2e368678cfa32171324fa35f6f4f1a0ec3f8b16e", "mcrit-pr-family-rename-same-name.md"),
    ("edits", "fix/edit-length-checks", "c7481df3c7110b36c301b9cde364aade78fa7a0b", "mcrit-pr-edit-length-checks.md"),
    ("batch", "feat/batch-sample-lookup", "BATCH_SHA", "mcrit-pr-batch-sample-lookup.md"),
    ("selector", "feat/jobs-select-by-ids", "SELECTOR_SHA", "mcrit-pr-jobs-select-by-ids.md"),
]

#: the MCRITweb follow-ups, pushed from r0ny123/mcritweb to familiary/mcritweb under the same name
#: and opened there, in this order: key, branch, head, base branch, head the base must have, text, draft
FOLLOWUPS = [
    ("f202", "fix/202-export-bytes", "F202_SHA", "fix/207-check-then-fetch", "4cb8db7fe4969fcd47d4122a437c89b8e1c0f490", "fix-202-export-bytes.md", False),
    ("f191", "fix/191-batch-lookups", "F191_SHA", "fix/191-serial-entry-fetches", "a25e2df60e7a350d3a3cb333436da1ae0e9ae65e", "fix-191-batch-lookups.md", True),
    ("f192", "fix/192-queue-reads-by-sample", "F192_SHA", "fix/192-bounded-collections", "59c7da11aeb91bc4d9c4847734ad64bbee36812c", "fix-192-queue-reads-by-sample.md", True),
]

#: what to search for before filing, per issue; the related PRs that are not duplicates are listed
SEARCHES = {
    "rename": ["modifyFamily", "rename family", "family rename", "family name KeyError", "family deleted"],
    "edits": ["family_name", "0-64", "empty version", "version component", "on_put"],
    "selector": ["getQueueData", "jobs sample", "sample_ids", "job_ids", "queue filter"],
    "batch": ["batch sample", "getSamplesByIds", "getSampleEntriesByIds", "samples by ids"],
}
KNOWN_RELATED = {168: "moves /jobs filter and state into the query (the selector issue cites it)",
                 183: "honours raw_responses in the client (cited on familiary #202)"}

#: familiary PR descriptions: branch -> [(sentence as opened, or a tuple of the forms it may have now, sentence with the numbers)]
BODY_CHANGES = {
    "fix/191-serial-entry-fetches": [
        (("The mcrit issue asking for it still needs to be filed.",
          # the one-line edit suggested for #221 before the mcrit PR existed
          "The mcrit issue asking for it is danielplohmann/mcrit#BATCH."),
         "The mcrit issue asking for it is danielplohmann/mcrit#BATCH, and danielplohmann/mcrit#BATCHPR implements it."),
    ],
    "fix/192-bounded-collections": [
        ("The full proposal is written up as a ready-to-file mcrit issue. **It still needs filing** against danielplohmann/mcrit; this PR does not file it.",
         "The full proposal is danielplohmann/mcrit#SELECTOR, and danielplohmann/mcrit#SELECTORPR implements it."),
        ("until mcrit gets the `sample_ids` selector, and that issue still has to be filed.",
         "until mcrit gets the `sample_ids` selector (danielplohmann/mcrit#SELECTOR, implemented in danielplohmann/mcrit#SELECTORPR)."),
    ],
    "fix/189-explore-sleeps": [
        ("while its message says 0-64 are allowed).",
         "while its message says 0-64 are allowed; reported as danielplohmann/mcrit#EDITS, fixed in danielplohmann/mcrit#EDITSPR)."),
    ],
    "fix/cross-job-unnamed-family": [
        ("refuses a family name shorter than two characters. So the samples there",
         "refuses a family name shorter than two characters (danielplohmann/mcrit#EDITS, fixed in danielplohmann/mcrit#EDITSPR). So the samples there"),
    ],
}

#: comments on familiary issues; #201 only when #208 does not already name it
CONDITIONAL_COMMENTS = {201: (208, "#201")}

#: the familiary PRs opened from the first handoff: number -> (branch, head, base)
FAM_PRS = {
    213: ("fix/182-cross-compare-lazy-tabs", "9185764db3e14155a9d963514375db7e443e221d", "master"),
    214: ("fix/183-poll-job-status", "633ae00b53d5a30769b4792b9e51500509e66d2d", "master"),
    215: ("fix/184-unique-blocks-cache", "5d2859a9f6cc43f10a6742c102af98753d0878b7", "master"),
    216: ("fix/186-function-diff-cache", "3d61cc1182bd57220a32b21551ecdd1a9e6b847e", "master"),
    217: ("fix/187-link-hunt-clusters", "be32d50a5de63aa822a11b1f8250f69f1e2adcdf", "master"),
    218: ("fix/188-diagram-drawing", "a99c64a709bd3c003a1da306b826b2eb721ead73", "master"),
    219: ("fix/189-explore-sleeps", "9bb08a0a5ee1994c4196ed60eb5803463eb31f8f", "master"),
    220: ("fix/190-request-row-reads", "9eaa3b4e122aafd93cdc667689f691ef707a4773", "master"),
    221: ("fix/191-serial-entry-fetches", "a25e2df60e7a350d3a3cb333436da1ae0e9ae65e", "master"),
    222: ("fix/192-bounded-collections", "59c7da11aeb91bc4d9c4847734ad64bbee36812c", "master"),
    223: ("fix/193-jobs-for-sample-once", "a94c27b7f1da1e81a863a60058c9d6a3eab66b89", "master"),
    224: ("fix/194-result-view-passes", "1236323dabc9462d50425703db5de5f7d3633b82", "master"),
    225: ("fix/197-link-hunt-links", "96978e37c72f9c9d9c101d27c07d1d908f51c29a", "master"),
    226: ("fix/198-cross-tooltips-job-grouping", "879a54c560039e04424dd3db19e61d9b4498a868", "fix/182-cross-compare-lazy-tabs"),
    227: ("fix/199-users-page-single-pass", "0c321e93696eef12f1588f95612a2c2c73c19c08", "master"),
    228: ("fix/200-api-passthrough-bytes", "e80b9574d8ad2929c03363da04e714ed17101810", "master"),
    229: ("fix/202-result-cache-size", "125b90c779b95323ce30b6fc266bd49f6b92c8d1", "master"),
    230: ("fix/204-cfg-loops", "792df759683e8817fbe97a4b8a514955ee5f3c9e", "master"),
    231: ("fix/206-admin-account-handlers", "9252805b0ecd7d17f5f4963de5056832039fb8b6", "master"),
    232: ("fix/207-check-then-fetch", "4cb8db7fe4969fcd47d4122a437c89b8e1c0f490", "master"),
    234: ("fix/linkhunt-empty-family-count", "9508923f47673b0b479e451fae5461954330a7cf", "master"),
    236: ("fix/cross-job-unnamed-family", "947b4238a53d0de9b2cd059f03f3e40686e153e8", "master"),
}

PLACEHOLDER = re.compile(r"#(RENAMEPR|EDITSPR|BATCHPR|SELECTORPR|F191PR|F192PR|F202PR|RENAME|EDITS|BATCH|SELECTOR)\b")
FOOTER = re.compile(r"claude|generated with|co-authored|anthropic", re.IGNORECASE)


def gh(*args, check=True):
    result = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.exit(f"gh {' '.join(args[:4])} ... failed: {result.stderr.strip()}")
    return result.stdout


def gh_json(*args):
    return json.loads(gh(*args) or "null")


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    return {}


def save_state(state):
    with open(STATE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=1, sort_keys=True)


def read_text(name):
    """Title and body of a prepared text: line 1 is `Title: ...`, the body starts at line 3."""
    with open(os.path.join(HERE, name), encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    if not lines[0].startswith("Title: ") or lines[1] != "":
        sys.exit(f"{name}: expected 'Title: ...' and an empty line")
    return lines[0][len("Title: "):], "\n".join(lines[2:]).rstrip("\n") + "\n"


def read_comment(name):
    with open(os.path.join(HERE, "comments", name), encoding="utf-8") as handle:
        return handle.read().rstrip("\n") + "\n"


def numbers(state):
    values = {}
    for key in ("rename", "edits", "selector", "batch"):
        if key in state.get("issues", {}):
            values[key.upper()] = state["issues"][key]
        if key in state.get("prs", {}):
            values[key.upper() + "PR"] = state["prs"][key]
    for key, number in state.get("followups", {}).items():
        values[key.upper() + "PR"] = number
    return values


def substitute(text, state, what, dry_run=False):
    """Fill in the issue and PR numbers. A dry run shows a number that doesn't exist yet as #<NAME>."""
    values = numbers(state)
    missing = sorted({token for token in PLACEHOLDER.findall(text) if token not in values})
    if missing and not dry_run:
        sys.exit(f"{what}: no number yet for {', '.join('#' + token for token in missing)}; run the earlier steps first")
    return PLACEHOLDER.sub(lambda match: "#%d" % values[match.group(1)] if match.group(1) in values else "#<%s>" % match.group(1), text)


def with_body_file(text, action):
    # newline="": the text goes out with the line endings it has
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8", newline="") as handle:
        handle.write(text)
    try:
        return action(handle.name)
    finally:
        os.unlink(handle.name)


def number_from_url(url):
    match = re.search(r"/(?:issues|pull)/(\d+)\s*$", url.strip())
    if not match:
        sys.exit(f"could not read a number from {url!r}")
    return int(match.group(1))


def check_login():
    login = gh("api", "user", "--jq", ".login").strip()
    if login != ME:
        sys.exit(f"gh is logged in as {login!r}, not {ME}")


def step_search(args, state):
    """List every issue and PR on danielplohmann/mcrit that the new ones could duplicate."""
    for key, queries in SEARCHES.items():
        seen = {}
        for query in queries:
            for hit in gh_json("search", "issues", query, "--repo", MCRIT, "--include-prs", "--json", "number,title,state,isPullRequest,url", "--limit", "30"):
                seen[hit["number"]] = hit
        print(f"\n== {key}: {len(seen)} candidates for {', '.join(repr(q) for q in queries)}")
        for number in sorted(seen):
            hit = seen[number]
            note = f"  <- known, {KNOWN_RELATED[number]}" if number in KNOWN_RELATED else ""
            print(f"  #{number} [{'PR' if hit['isPullRequest'] else 'issue'}, {hit['state']}] {hit['title']}{note}")
    print("\nRead every candidate whose title is close. A real duplicate means: stop, and report it.")


def step_issues(args, state):
    state.setdefault("issues", {})
    if "batch" not in state["issues"]:
        found = gh_json("issue", "list", "--repo", MCRIT, "--author", ME, "--state", "all", "--search", f"{BATCH_TITLE} in:title", "--json", "number,title,state")
        found = [issue for issue in found if issue["title"].startswith(BATCH_TITLE)]
        if len(found) != 1:
            sys.exit(f"expected one issue by {ME} titled '{BATCH_TITLE}...', found {len(found)}; record it with --set batch=N")
        print(f"batch: #{found[0]['number']} {found[0]['title']} ({found[0]['state']})")
        state["issues"]["batch"] = found[0]["number"]
    for key, name in ISSUES:
        title, body = read_text(name)
        if key in state["issues"]:
            print(f"{key}: already #{state['issues'][key]}")
            continue
        existing = gh_json("issue", "list", "--repo", MCRIT, "--state", "all", "--search", f'"{title}" in:title', "--json", "number,title")
        existing = [issue for issue in existing if issue["title"] == title]
        if existing:
            print(f"{key}: already filed as #{existing[0]['number']}")
            state["issues"][key] = existing[0]["number"]
            continue
        body = substitute(body, state, name, dry_run=not args.apply)
        if not args.apply:
            print(f"{key}: would file '{title}' ({len(body)} characters)")
            continue
        url = with_body_file(body, lambda path: gh("issue", "create", "--repo", MCRIT, "--title", title, "--body-file", path))
        state["issues"][key] = number_from_url(url)
        save_state(state)
        print(f"{key}: filed {url.strip()}")


def step_prs(args, state):
    state.setdefault("prs", {})
    for key, branch, sha, name in PRS:
        title, body = read_text(name)
        head = subprocess.run(["git", "ls-remote", FORK, f"refs/heads/{branch}"], capture_output=True, text=True, check=True).stdout.split()
        if not head or head[0] != sha:
            sys.exit(f"{branch}: r0ny123/mcrit has {head[0] if head else 'nothing'}, expected {sha}. Stop and report.")
        if key in state["prs"]:
            print(f"{key}: already #{state['prs'][key]}")
            continue
        open_prs = [pr for pr in gh_json("pr", "list", "--repo", MCRIT, "--state", "open", "--head", branch, "--json", "number,headRefName,headRepositoryOwner")
                    if pr["headRefName"] == branch and pr["headRepositoryOwner"]["login"] == ME]
        if open_prs:
            print(f"{key}: already open as #{open_prs[0]['number']}")
            state["prs"][key] = open_prs[0]["number"]
            continue
        body = substitute(body, state, name, dry_run=not args.apply)
        if not args.apply:
            print(f"{key}: would open '{title}' from {ME}:{branch} @ {sha[:7]} against main")
            continue
        url = with_body_file(body, lambda path: gh("pr", "create", "--repo", MCRIT, "--base", "main", "--head", f"{ME}:{branch}", "--title", title, "--body-file", path))
        state["prs"][key] = number_from_url(url)
        save_state(state)
        print(f"{key}: opened {url.strip()}")


def remote_head(url, branch):
    """The commit a branch points to on a remote, or None when it has no such branch."""
    heads = subprocess.run(["git", "ls-remote", url, f"refs/heads/{branch}"], capture_output=True, text=True, check=True).stdout.split()
    return heads[0] if heads else None


def step_followups(args, state):
    """Push each follow-up from r0ny123/mcritweb to familiary/mcritweb under the same name, as the
    first 22 were, and open its PR on the base it is stacked on."""
    state.setdefault("followups", {})
    upstream = f"https://github.com/{FAM}"
    for key, branch, sha, base, base_sha, name, draft in FOLLOWUPS:
        title, body = read_text(name)
        if key in state["followups"]:
            print(f"{key}: already #{state['followups'][key]}")
            continue
        open_prs = [pr for pr in gh_json("pr", "list", "--repo", FAM, "--state", "open", "--head", branch, "--json", "number,headRefName") if pr["headRefName"] == branch]
        if open_prs:
            print(f"{key}: already open as #{open_prs[0]['number']}")
            state["followups"][key] = open_prs[0]["number"]
            continue
        fork_head = remote_head(FORK_WEB, branch)
        if fork_head != sha:
            sys.exit(f"{branch}: r0ny123/mcritweb has {fork_head or 'nothing'}, expected {sha}. Stop and report.")
        if remote_head(upstream, base) != base_sha:
            sys.exit(f"{branch}: its base {base} on {FAM} is not at {base_sha[:7]} any more. Stop and report.")
        upstream_head = remote_head(upstream, branch)
        if upstream_head not in (None, sha):
            sys.exit(f"{branch}: {FAM} already has a different branch of that name ({upstream_head[:7]}). Stop and report.")
        body = substitute(body, state, name, dry_run=not args.apply)
        kind = "draft PR" if draft else "PR"
        if not args.apply:
            push = "push it there and " if upstream_head is None else ""
            print(f"{key}: would {push}open a {kind} '{title}' from {branch} @ {sha[:7]} against {base}")
            continue
        if upstream_head is None:
            with tempfile.TemporaryDirectory() as scratch:
                subprocess.run(["git", "init", "--quiet", "--bare", scratch], check=True)
                subprocess.run(["git", "-C", scratch, "fetch", "--quiet", FORK_WEB, f"refs/heads/{branch}"], check=True)
                # a new branch, so no force: a push that would overwrite anything is refused
                subprocess.run(["git", "-C", scratch, "push", "--quiet", upstream, f"{sha}:refs/heads/{branch}"], check=True)
            print(f"{key}: pushed {branch} @ {sha[:7]} to {FAM}")
        create = ["pr", "create", "--repo", FAM, "--base", base, "--head", branch, "--title", title]
        url = with_body_file(body, lambda path: gh(*create, "--body-file", path, *(["--draft"] if draft else [])))
        state["followups"][key] = number_from_url(url)
        save_state(state)
        print(f"{key}: opened {kind} {url.strip()}")


def find_fam_pr(branch):
    prs = [pr for pr in gh_json("pr", "list", "--repo", FAM, "--state", "open", "--head", branch, "--json", "number,headRefName,author,body") if pr["headRefName"] == branch]
    if len(prs) != 1:
        sys.exit(f"{branch}: expected one open PR on {FAM}, found {len(prs)}")
    if prs[0]["author"]["login"] != ME:
        sys.exit(f"{branch}: PR #{prs[0]['number']} is by {prs[0]['author']['login']}, not {ME}")
    return prs[0]


def step_bodies(args, state):
    for branch, changes in BODY_CHANGES.items():
        pr = find_fam_pr(branch)
        body = updated = pr["body"]
        shown = []
        for olds, new in changes:
            new = substitute(new, state, branch)
            if new in updated:
                print(f"#{pr['number']} {branch}: already says {new[:70]!r}...")
                continue
            olds = [substitute(old, state, branch) for old in (olds if isinstance(olds, tuple) else (olds,))]
            present = [old for old in olds if updated.count(old) == 1]
            if len(present) != 1:
                sys.exit(f"#{pr['number']} {branch}: expected one of {[old[:60] for old in olds]} once. Stop and report.")
            updated = updated.replace(present[0], new)
            shown.append((present[0], new))
        if updated == body:
            continue
        print(f"#{pr['number']} {branch}:")
        for old, new in shown:
            print(f"  - {old}\n  + {new}")
        if args.apply:
            with_body_file(updated, lambda path: gh("pr", "edit", str(pr["number"]), "--repo", FAM, "--body-file", path))
            print(f"#{pr['number']}: description updated")


def step_comments(args, state):
    names = sorted(name for name in os.listdir(os.path.join(HERE, "comments")) if re.fullmatch(r"issue-\d+\.md", name))
    for name in names:
        number = int(re.search(r"\d+", name).group(0))
        body = substitute(read_comment(name), state, name)
        if number in CONDITIONAL_COMMENTS:
            pr_number, needle = CONDITIONAL_COMMENTS[number]
            pr = gh_json("pr", "view", str(pr_number), "--repo", FAM, "--json", "title,body")
            if needle in (pr["title"] or "") + (pr["body"] or ""):
                print(f"#{number}: skipped, #{pr_number} already names it")
                continue
        issue = gh_json("issue", "view", str(number), "--repo", FAM, "--json", "state,comments,title")
        first_line = body.split("\n", 1)[0].strip()
        if any(comment["author"]["login"] == ME and comment["body"].strip().split("\n", 1)[0].strip() == first_line for comment in issue["comments"]):
            print(f"#{number}: skipped, already commented")
            continue
        if issue["state"] != "OPEN":
            print(f"#{number}: skipped, the issue is {issue['state'].lower()}")
            continue
        if not args.apply:
            print(f"#{number} ({issue['title']}): would comment, starting {first_line[:80]!r}")
            continue
        with_body_file(body, lambda path: gh("issue", "comment", str(number), "--repo", FAM, "--body-file", path))
        print(f"#{number}: commented")


def ci_summary(repo, number):
    """The checks of a PR, counted by outcome, with the names of any that did not pass."""
    result = subprocess.run(["gh", "pr", "checks", str(number), "--repo", repo, "--json", "name,bucket"], capture_output=True, text=True)
    try:
        checks = json.loads(result.stdout)
    except ValueError:
        return (result.stdout or result.stderr).strip().replace("\n", " | ")[:160] or "no checks reported"
    if not checks:
        return "no checks reported"
    counts = {}
    for check in checks:
        counts[check["bucket"]] = counts.get(check["bucket"], 0) + 1
    others = [check["name"] for check in checks if check["bucket"] not in ("pass", "skipping")]
    return ", ".join(f"{count} {bucket}" for bucket, count in sorted(counts.items())) + (f" ({', '.join(others)})" if others else "")


def step_verify(args, state):
    problems = []
    print("== familiary/mcritweb PRs")
    for number, (branch, sha, base) in FAM_PRS.items():
        pr = gh_json("pr", "view", str(number), "--repo", FAM, "--json", "headRefName,headRefOid,baseRefName,author,state,body,title")
        ok = pr["headRefName"] == branch and pr["headRefOid"] == sha and pr["baseRefName"] == base and pr["author"]["login"] == ME
        clean = not FOOTER.search(pr["title"] + "\n" + pr["body"])
        print(f"  #{number} {branch}: {'ok' if ok else 'MISMATCH'}, {'no footer' if clean else 'FOOTER FOUND'}, {pr['state'].lower()}")
        if not ok or not clean:
            problems.append(f"familiary #{number}")
    print("== familiary/mcritweb follow-ups")
    for key, branch, sha, base, base_sha, name, draft in FOLLOWUPS:
        if key not in state.get("followups", {}):
            print(f"  {key}: not opened yet")
            continue
        pr = gh_json("pr", "view", str(state["followups"][key]), "--repo", FAM, "--json", "headRefName,headRefOid,baseRefName,author,state,isDraft,body,title,url")
        ok = pr["headRefName"] == branch and pr["headRefOid"] == sha and pr["baseRefName"] == base and pr["author"]["login"] == ME and pr["isDraft"] == draft
        clean = not FOOTER.search(pr["title"] + "\n" + pr["body"]) and not PLACEHOLDER.search(pr["body"])
        print(f"  #{state['followups'][key]} {branch}: {'ok' if ok else 'MISMATCH'}{' (draft)' if pr['isDraft'] else ''}, {'clean' if clean else 'FOOTER OR PLACEHOLDER FOUND'}, {pr['state'].lower()} {pr['url']}")
        if not ok or not clean:
            problems.append(f"familiary follow-up {key}")
    print("== danielplohmann/mcrit PRs")
    for key, branch, sha, name in PRS:
        if key not in state.get("prs", {}):
            print(f"  {key}: not opened yet")
            continue
        pr = gh_json("pr", "view", str(state["prs"][key]), "--repo", MCRIT, "--json", "headRefName,headRefOid,baseRefName,author,state,body,title,url")
        ok = pr["headRefName"] == branch and pr["headRefOid"] == sha and pr["baseRefName"] == "main" and pr["author"]["login"] == ME
        clean = not FOOTER.search(pr["title"] + "\n" + pr["body"]) and not PLACEHOLDER.search(pr["body"])
        print(f"  #{state['prs'][key]} {branch}: {'ok' if ok else 'MISMATCH'}, {'clean' if clean else 'FOOTER OR PLACEHOLDER FOUND'}, {pr['state'].lower()} {pr['url']}")
        if not ok or not clean:
            problems.append(f"mcrit {key} PR")
    print("== danielplohmann/mcrit issues")
    for key, number in sorted(state.get("issues", {}).items()):
        issue = gh_json("issue", "view", str(number), "--repo", MCRIT, "--json", "title,body,author,state,url")
        clean = not FOOTER.search(issue["title"] + "\n" + issue["body"]) and not PLACEHOLDER.search(issue["body"])
        print(f"  {key}: #{number} {issue['state'].lower()} by {issue['author']['login']}, {'clean' if clean else 'FOOTER OR PLACEHOLDER FOUND'} {issue['url']}")
        if not clean:
            problems.append(f"mcrit issue {key}")
    print("== CI (report only)")
    for repo, pr_numbers in ((FAM, list(FAM_PRS) + sorted(state.get("followups", {}).values())), (MCRIT, sorted(state.get("prs", {}).values()))):
        for number in pr_numbers:
            print(f"  {repo} #{number}: {ci_summary(repo, number)}")
    print("\nproblems: " + (", ".join(problems) if problems else "none"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("step", choices=["search", "issues", "prs", "followups", "bodies", "comments", "verify"])
    parser.add_argument("--apply", action="store_true", help="make the changes; without it, only print them")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=N", help="record an issue or PR number by hand")
    args = parser.parse_args()
    state = load_state()
    for item in args.set:
        key, _, value = item.partition("=")
        if key in ("f191", "f192", "f202"):
            section = "followups"
        else:
            section, key = ("prs", key[: -len("_pr")]) if key.endswith("_pr") else ("issues", key)
            if key not in ("rename", "edits", "selector", "batch"):
                key = ""
        if not key or not value.isdigit():
            sys.exit(f"--set {item}: expected rename|edits|selector|batch[_pr]=N or f191|f192|f202=N")
        state.setdefault(section, {})[key] = int(value)
    save_state(state)
    check_login()
    steps = {"search": step_search, "issues": step_issues, "prs": step_prs, "followups": step_followups, "bodies": step_bodies, "comments": step_comments, "verify": step_verify}
    steps[args.step](args, state)
    save_state(state)
    if not args.apply and args.step in ("issues", "prs", "followups", "bodies", "comments"):
        print("\nDry run: nothing was changed. Add --apply to make these changes.")


if __name__ == "__main__":
    main()
