This is mostly moot once #222 is merged. That PR removes the only call site that embedded the whole family list (`templates/table/submit_or_query_dropzone.html:236` at e4bfa55). Afterwards every family type-ahead gets at most 10 candidates from `explore.family_names`, so normalizing the lookup and the labels per keystroke comes to 10 labels' worth of work.

The redundancy that is left sits inside `static/autocomplete.js`, which is vendored and not ours to patch. Fixing it would mean overriding `createItem` from our own script, for no measurable gain at 10 candidates.

I'd close this once #222 is merged.
