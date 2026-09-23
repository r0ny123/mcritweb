Title: Sample and family edits refuse the empty and one-character values their messages allow

`PUT /samples/<id>` and `PUT /families/<id>` check their fields with patterns that are stricter than the messages they answer with:

| field | check | message | refused although the message allows it |
|---|---|---|---|
| `family_name` (both routes) | `^(?=[a-zA-Z0-9._\-]{0,64}$)(?!.*[\-_.]{2})[^\-_.].*[^\-_.]$` | "family_name may be 0-64 alphanumeric chars with single dots, dashes, underscores inbetween." | `""` and every one-character name |
| `version` | `^[ -~]{1,64}$` | "version may be 0-64 printable characters." | `""` |
| `component` | `^[ -~]{1,64}$` | "component may be 0-64 printable characters." | `""` |

The family pattern's lookahead allows 0-64 characters, but `[^\-_.].*[^\-_.]` then needs a first and a last character, so at least two.

Reproduced against 1.9.0. main has the same checks, in `SampleResource.on_put` and `FamilyResource.on_put`:

```
PUT /samples/16 {"family_name": ""}   -> 400 family_name may be 0-64 alphanumeric chars ...
PUT /samples/16 {"family_name": "x"}  -> 400 family_name may be 0-64 alphanumeric chars ...
PUT /samples/16 {"family_name": "ab"} -> 202 Sample modified.
PUT /samples/16 {"version": ""}       -> 400 version may be 0-64 printable characters.
PUT /samples/16 {"component": ""}     -> 400 component may be 0-64 printable characters.
```

What this blocks:
- `""` is what mcrit itself stores for a sample submitted without a version or component, so once either is set, the API can't clear it again.
- `""` is also the name of family 0, the unnamed family: `MongoDbStorage` creates it with `family_name=""`, and `addFamily("")` resolves to it. So no sample can be moved into the unnamed family, and no family merged into it, through the API.
- `on_post_submit_binary` passes `family` and `version` through unchecked. A sample can be submitted into a family named `x`, but no sample can be moved into that family afterwards.

If the messages state the intent, these patterns match it:
- `family_name`: `^(?![\-_.])(?!.*[\-_.]{2})(?!.*[\-_.]\Z)[a-zA-Z0-9._\-]{0,64}\Z`, one rule per lookahead: no separator first, none doubled, none last.
- `version` and `component`: `^[ -~]{0,64}\Z`.

They end in `\Z` rather than `$`, because in Python `$` also matches before a trailing newline. Today that lets `"ab\n"` through as a family name and `"1.0\n"` as a version, and with `{0,64}` it would let a lone `"\n"` through as an empty value.

Compared over 37,210 strings (every length from 0 to 69, letters, digits, separators, spaces, tabs, newlines and non-ASCII), the new patterns accept exactly what the current ones accept, plus `""` and single alphanumeric characters, minus values ending in a newline. A lone `-`, `_` or `.` stays refused, since separators only go between characters.

Renaming family 0 to `""` then becomes possible through the API too. That is a rename of a family to its own name, a case with a bug of its own: #RENAME.

Found from MCRITweb, whose sample edit form sends an emptied version field as `""`.
