Title: Leave a family alone when it is renamed to its own name

## Summary
Fixes #RENAME.

Renaming a family to the name it already has deleted it in MongoDbStorage and raised `KeyError` in MemoryStorage, and for family 0 it would double the counters. It is now a no-op for the name, and the rest of the update still applies. A second commit fixes an ordinary rename in MemoryStorage, which failed whenever the renamed family's samples were not the last ones stored.

## What changed
- `MongoDbStorage.modifyFamily` and `MemoryStorage.modifyFamily`: the rename block runs only when the new name differs from the family's stored one (`family_name != old_family_info.family_name`). The `is_library` part before it is unchanged.
- `MemoryStorage.modifyFamily`: the pichash entries of the moved functions are re-keyed with `function_entry.sample_id`. They used `sample_id`, left over from the loop over all samples just above it, which is the last sample stored.
- `tests/testStorage.py`: three tests in `MemoryStorageTest`, so they run on both storages through `MongoDbStorageTest`:
  - `testRenamingAFamilyToItsOwnNameChangesNothing`: a named family and family 0 are each renamed to their own name. The families stay, their counters equal the stored samples and functions, and an `is_library` change in the same update still applies.
  - `testRenamingAFamilyToItsOwnNameLeavesAnotherOfTheSameNameAlone`: a second family is given the first one's name directly in storage, then renamed to it. Both families keep their counters, and its sample stays with it.
  - `testRenamingAFamilyReindexesEachFunctionUnderItsOwnSample`: two samples in two families; the first family is renamed. Every function of the moved sample is found under the new family and its own sample, and not under the old family.

## Why
`modifyFamily` merges the renamed family into whichever family `addFamily(name)` returns: it adds the counters of both, deletes the old family, and moves the samples and functions over. With the family's own name, `addFamily` returns the family itself:
- MongoDbStorage deleted the family document, then updated the one it had just deleted. `getFamily` answered None, and the family disappeared from `/families`, while its samples and functions kept its id.
- MemoryStorage popped the family, then raised `KeyError` on the lookup after.
- Family 0, named `""`, isn't popped, but both sides of the merge are family 0, so its counters doubled.

`PUT /families/<id>` with the family's current name reaches this for any named family. MCRITweb's edit form drops an unchanged name, but the REST API and `McritClient.modifyFamily` pass it through. Family 0 can't be renamed through the API today, because `""` fails the `family_name` check, which #EDITS is about.

The check compares the new name with the stored one instead of resolving it with `getFamilyId`, because names are not unique in storage. `recomputeFamilyStats` re-creates a missing family document under the name its samples carry, whatever other family has it (`_ensureFamilyDocument`, #151). With a shared name, `getFamilyId` can answer the other family, and a rename to the family's own name would merge it into that one.

## Validation
- Without the fix, the first test fails on both storages: MemoryStorage with `KeyError: 1`, MongoDbStorage with `AssertionError: unexpectedly None` right after the rename. Family 0's doubling shows on MongoDbStorage once the named family's check is out of the way: `{'num_samples': 2, 'num_functions': 20, ...}` for one sample of 10 functions.
- With the name looked up (`getFamilyId(family_name) != family_id`) instead of compared, the shared-name test fails on both storages: the other family absorbs this one, `{'num_samples': 1, 'num_functions': 10, ...} != {'num_samples': 2, 'num_functions': 20, ...}`.
- Without the second commit, the reindexing test fails on MemoryStorage with `KeyError: (1, 1, 0)` and passes on MongoDbStorage, which has no such index.
- Full suite against MongoDB 8.0: 325 passed, 49 subtests (main at 2ac8d7b: 319 passed, 49 subtests). `ruff format --check`, `ruff check` and `ty check` are clean.
- Live, against a 1.9.0 corpus of 66 samples:
  - I moved one sample into a throwaway family, then sent `PUT /families/<id>` with that family's own name.
  - With the 1.9.0 worker, the family was gone afterwards: `GET /families/19` failed while the sample still had `family_id` 19.
  - With a worker running this branch, the family stayed, with its counts unchanged (`('tmpsame', 1, 1059, 0)` before and after). The queue shows that worker ran the job.
  - Both times the sample was moved back, and the family list ended identical to how it began.

## Limitations
- A rename to the family's own name now writes nothing in MongoDbStorage, so it doesn't advance `db_state` there. MemoryStorage advances `db_state` on every `modifyFamily` call, as it did before, including one that changes nothing.
- Only the storage changed. `PUT /families/<id>` with the family's own name still answers 202 "Family modified.", which is true in the sense that the update was applied, and matches what `PUT /samples/<id>` answers for a move into the sample's own family.

## Changelog
A proposed `[Unreleased]` entry. It isn't in the branch, so that this PR and the other open ones don't conflict in the same section:

> ### Fixed
> - Renaming a family to its own name deleted it on MongoDB, while its samples and functions kept its id, and raised `KeyError` on MemoryStorage; for family 0, named `""`, it doubled the counters. MemoryStorage also failed an ordinary rename whenever the renamed family's samples were not the last ones stored ([#RENAME]).

## Merge conflicts
- None. The branch merges cleanly with every open PR, including #176, #177 and #178, which also touch the storages and `tests/testStorage.py`.
- #177 merges the actor lists inside the rename block. With this change a rename to the family's own name skips that block, which leaves the family's own actors as they are.
