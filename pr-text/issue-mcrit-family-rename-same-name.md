Title: Renaming a family to its own name deletes it, and MemoryStorage can't rename a family

`modifyFamily` resolves the new name with `addFamily` and merges the old family into the family it names. When the name is the family's own, `addFamily` returns the family itself, and merging a family into itself goes wrong in both storages:

- **MongoDbStorage** deletes the family document (`families.delete_one`), then updates the document it just deleted. The family disappears from `GET /families` and `getFamily` answers None, while its samples and functions keep its id.
- **MemoryStorage** pops the family, then raises `KeyError` on the lookup after.
- **Family 0**, whose name is `""`: both sides of the merge are family 0, so its counters double. The API can't reach this today, because `""` fails the `family_name` check, but the storage can, and accepting `""` there, as its message promises, would open it.

`PUT /families/<id>` with the family's current `family_name` reaches the first two for any named family. MCRITweb's edit form drops an unchanged name before it calls the client. The REST API and `McritClient.modifyFamily` don't.

Reproduced on main (77db150) with a scratch database: one sample submitted with family `abc`, then `modifyFamily(1, {"family_name": "abc"})`. MongoDbStorage answered True, and afterwards `getFamily(1)` was None while the sample still had `family_id` 1. MemoryStorage raised `KeyError: 1`.

While tracing this, I found a second bug in `MemoryStorage.modifyFamily`, which breaks ordinary renames. It re-keys each moved function's pichash entry with `sample_id`, the variable left over from the loop over all samples just before it. That is the last sample stored, not the function's own sample. So the `remove` misses and raises `KeyError` whenever the renamed family's samples are not the last ones stored. With two samples in two families, renaming the first family fails with `KeyError: (1, 1, 0)`. MongoDbStorage keeps no such index and is not affected.

Fix direction: skip the merge when the name is the family's stored one, and use `function_entry.sample_id` in MemoryStorage's re-keying.
