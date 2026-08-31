"""What `static/autocomplete.js` may safely be handed.

The widget is vendored and may not be patched (AGENTS.md). It builds each suggestion
as an HTML string and assigns it to `innerHTML`, and interpolates the same value into
`data-label` / `data-value`, so a family name reaching it is markup rather than text -
and a family name is whatever whoever submits or renames a family typed. `|tojson`
delivers the value into the script correctly and does nothing about what the script
then does with it, which is the whole of issue #85's lesson.

One function, in a module of its own, because there are now two producers and they
have to escape identically:

  * the `autocomplete_items` Jinja filter, for the call site that still ships the list
    with the page (the `submit_or_query_dropzone` macro) - issue #68;
  * `explore.family_names`, the JSON endpoint the family type-ahead fetches from as
    the user types - issue #77.

`escape` stringifies, so a non-string name arrives as e.g. "None" rather than being
passed through. Family names are always strings off the backend, and the loop this
replaced handed `null` to `removeDiacritics()`, which threw and took the whole
type-ahead with it - so this is not a regression, but it is a change.
"""
from markupsafe import escape

#: The key both producers put the items under. Named after the filter on purpose:
#: `tests/testAutocompleteEscaping.py` accepts a `setData()` fed from this field and
#: nothing else off a response, so the name is part of the guarantee rather than
#: decoration.
RESPONSE_KEY = "autocomplete_items"


def autocomplete_items(names):
    """`[{"label": ..., "value": ...}]`, HTML-escaped, for one list of names."""
    return [{"label": str(escape(name)), "value": str(escape(name))} for name in names]
