#!/usr/bin/python
"""`/explore/functions` hands the table entries, not raw dicts off the wire. Issue #64.

`McritClient._search_base` returns `handle_response(response)` untouched, so the values
under `search_results` are dicts, while every other accessor on the client
(`getFunctionById`, `getFamilies`, ...) returns typed entries. Making the client itself
deserialize is an mcrit change and is what the issue asks for.

The mcritweb half is that its two function listings disagreed about it. `explore.search`
called `FunctionEntry.fromDict` on those values; `explore.functions` had that call
commented out and appended the dict. Both feed the same `function_table` macro.

Today that difference is invisible - Jinja falls back from attribute lookup to item
lookup, and the wire keys happen to equal the attribute names - which is exactly why it
was worth closing rather than leaving. A renamed key, or any property derived rather
than stored, would have broken one page while leaving the other working, and the suite
would have said nothing.
"""

import logging
import unittest

import pytest
from flask import template_rendered
from mcrit.storage.FunctionEntry import FunctionEntry

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


@pytest.fixture
def rendered(app):
    """(template, context) for every template rendered during a request."""
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    yield recorded
    template_rendered.disconnect(record, app)


def context_for(rendered, name):
    for template, context in rendered:
        if template.name == name:
            return context
    raise AssertionError(f"{name} was not rendered; got {[t.name for t, _ in rendered]}")


def test_the_function_listing_passes_entries_rather_than_wire_dicts(client, as_role, fake_mcrit, rendered):
    as_role("visitor")

    client.get("/explore/functions")

    functions = context_for(rendered, "functions.html")["functions"]
    assert functions, "the corpus rendered no functions, so this proves nothing"
    assert all(isinstance(function, FunctionEntry) for function in functions), (
        f"got {sorted({type(function).__name__ for function in functions})}"
    )


def test_the_search_page_agrees(client, as_role, fake_mcrit, rendered):
    """The half that was already right. Asserted so the two cannot drift apart again
    from the other direction.

    Searched by id rather than by name: the captured functions all have an empty
    `function_name`, so a text query matches none of them and `explore.search` would
    return with nothing to deserialize - a test that proves nothing.
    """
    as_role("visitor")
    function = next(iter(fake_mcrit._functions.values()))

    client.get(f"/explore/search?query={function.function_id}&type=function")

    functions = context_for(rendered, "search.html")["functions"]
    assert functions, "the search returned no functions, so this proves nothing"
    assert all(isinstance(item, FunctionEntry) for item in functions)


def test_both_listings_render_the_same_row_for_the_same_function(client, as_role, fake_mcrit):
    """The user-visible invariant behind the type assertions: whatever the two routes
    hand the shared macro, one function must look the same on both pages."""
    as_role("visitor")
    function = next(iter(fake_mcrit._functions.values()))

    listing = client.get("/explore/functions?limit=25").get_data(as_text=True)
    search = client.get(f"/explore/search?query={function.function_id}&type=function").get_data(as_text=True)

    # the pichash link is what a function row is identified by; url_for percent-encodes
    # the colon, so match on the rendered hash rather than on the query string
    marker = f"0x{function.pichash:016x}"
    assert marker in listing, "the listing did not render the function at all"
    assert marker in search, "the search page did not render the function at all"


if __name__ == "__main__":
    unittest.main()
