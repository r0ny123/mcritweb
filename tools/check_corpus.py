"""Check the corpus in MongoDB on 127.0.0.1:27017 against what the snapshot holds, and that every
family's counters equal its samples and functions. Read-only. Run it after anything that writes
through the live API; a nonzero exit means the corpus is not what the snapshot restored.

usage: check_corpus.py [--quiet]
"""

import sys

import pymongo

EXPECTED = {"samples": 66, "families": 16, "functions": 26436}

db = pymongo.MongoClient("127.0.0.1", 27017, serverSelectionTimeoutMS=5000)["mcrit"]
stored = {f["family_id"]: (f["family_name"], f["num_samples"], f["num_functions"], f["num_library_samples"]) for f in db.families.find()}
by_family = {}
for sample in db.samples.find({}, {"family_id": 1, "is_library": 1}):
    counts = by_family.setdefault(sample["family_id"], [0, 0])
    counts[0] += 1
    counts[1] += int(bool(sample.get("is_library")))
functions = {row["_id"]: row["n"] for row in db.functions.aggregate([{"$group": {"_id": "$family_id", "n": {"$sum": 1}}}])}

found = {"samples": db.samples.count_documents({}), "families": len(stored), "functions": db.functions.estimated_document_count()}
drifted = [
    (family_id, name)
    for family_id, (name, num_samples, num_functions, num_library) in sorted(stored.items())
    if (num_samples, num_functions, num_library) != (by_family.get(family_id, [0, 0])[0], functions.get(family_id, 0), by_family.get(family_id, [0, 0])[1])
]
dangling = sorted(set(by_family) - set(stored))
problems = [f"{key}: {found[key]}, expected {EXPECTED[key]}" for key in EXPECTED if found[key] != EXPECTED[key]]
problems += [f"family {family_id} ({name!r}): counters differ from its samples and functions" for family_id, name in drifted]
problems += [f"samples point at family {family_id}, which has no document" for family_id in dangling]

if "--quiet" not in sys.argv:
    print(f"{found['samples']} samples, {found['families']} families, {found['functions']} functions, {db.queue.estimated_document_count()} jobs")
print("corpus: " + ("as in the snapshot" if not problems else "CHANGED\n  " + "\n  ".join(problems)))
sys.exit(1 if problems else 0)
