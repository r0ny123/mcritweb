#!/usr/bin/python
"""A listing page must find what the search page finds.

MCRIT answers a search with two things: `search_results`, the text hits, and `id_match`
(plus `sha_match` for samples), the exact hit on an identifier. `explore.search` reads
both. `explore.families`, `explore.samples` and `explore.functions` read only the first
and drop the other on the floor - so the same query, against the same backend, gave
opposite answers depending on which page you typed it into:

    /explore/functions?query=5              -> "No functions available"
    /explore/search?query=5&type=function   -> function 5

That is a search hiding a record that exists, which is worse than the cosmetic half of
issue #56 (marking those matches, which is what the issue text is about). Reproduced
live for families and functions; the samples path is the same code shape but the corpus
cannot demonstrate it, because every single-digit sample id is also a substring of some
sha256 and so arrives as a text hit anyway.

On the real backend `id_match` is populated for any bare integer (or 0x-integer) up to
0xFFFFFFFF that is a real id, and `sha_match` for any 64-hex string - see
mcrit/index/MinHashIndex.py.
"""

import logging
import unittest
from contextlib import contextmanager

import pytest
from flask import template_rendered

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


def row_count(response, kind):
    return response.get_data(as_text=True).count(f"parent_{kind}-table")


@pytest.mark.parametrize(
    "listing,search,kind,query",
    [
        ("/explore/families?query=2", "/explore/search?query=2&type=family", "family", "2"),
        ("/explore/functions?query=5", "/explore/search?query=5&type=function", "function", "5"),
    ],
)
def test_the_listing_page_finds_what_the_search_page_finds(client, as_role, listing, search, kind, query):
    as_role("visitor")

    on_the_listing = row_count(client.get(listing), kind)
    on_the_search_page = row_count(client.get(search), kind)

    assert on_the_search_page > 0, "the premise: the search page does find it"
    assert on_the_listing == on_the_search_page, \
        f"{listing} rendered {on_the_listing} rows where the search page rendered {on_the_search_page}"


@pytest.mark.parametrize(
    "path,kind,placeholder",
    [
        ("/explore/families?query=2", "family", "No families available"),
        ("/explore/functions?query=5", "function", "No functions available"),
    ],
)
def test_the_listing_page_does_not_claim_the_record_is_absent(client, as_role, path, kind, placeholder):
    """The visible symptom: the empty-table placeholder, shown for a record that exists.

    Asserted on the exact string the table macro emits, so this fails if the row stops
    being rendered - not on a phrase that could drift.
    """
    as_role("visitor")

    response = client.get(path)
    page = response.get_data(as_text=True)

    assert row_count(response, kind) > 0, "the record is not listed at all"
    assert placeholder not in page, f"{path} still shows {placeholder!r}"


def test_a_sample_sha256_reaches_the_samples_listing(client, as_role, fake_mcrit):
    """The samples page has the same shape. The corpus cannot stage the id half - every
    single-digit id is a substring of some sha256, so it arrives as a text hit anyway -
    so this drives the sha_match branch with a backend that answers only there."""
    as_role("visitor")
    known = fake_mcrit._samples[6]
    monkey = {
        "search_results": {},
        "cursor": {"forward": None, "backward": None},
        "id_match": None,
        "sha_match": known.toDict(),
    }
    fake_mcrit.search_samples = lambda *args, **kwargs: monkey

    response = client.get(f"/explore/samples?query={known.sha256}")

    assert response.status_code == 200
    assert row_count(response, "sample") == 1
    assert known.sha256[:8] in response.get_data(as_text=True)


def test_a_sample_id_match_reaches_the_samples_listing(client, as_role, fake_mcrit):
    as_role("visitor")
    known = fake_mcrit._samples[6]
    fake_mcrit.search_samples = lambda *args, **kwargs: {
        "search_results": {}, "cursor": {"forward": None, "backward": None},
        "id_match": known.toDict(), "sha_match": None,
    }

    response = client.get("/explore/samples?query=6")

    assert row_count(response, "sample") == 1


@pytest.mark.parametrize("kind,path", [("family", "/explore/families"), ("function", "/explore/functions"),
                                       ("sample", "/explore/samples")])
def test_an_exact_hit_that_is_also_a_text_hit_is_listed_once(client, as_role, fake_mcrit, kind, path):
    """The id match is prepended, and the same record can come back among the text hits
    - which is how issue #78 happened on the search page. Not repeating it here."""
    as_role("visitor")
    pool = {"family": fake_mcrit._families, "function": fake_mcrit._functions,
            "sample": fake_mcrit._samples}[kind]
    key = sorted(pool)[0]
    entry = pool[key]
    as_dict = entry if isinstance(entry, dict) else entry.toDict()
    result = {
        "search_results": {str(key): as_dict},
        "cursor": {"forward": None, "backward": None},
        "id_match": as_dict,
        "sha_match": None,
    }
    setattr(fake_mcrit, f"search_{kind}s" if kind != "family" else "search_families",
            lambda *args, **kwargs: result)

    response = client.get(f"{path}?query={key}")

    assert row_count(response, kind) == 1, "the exact hit was listed twice"


def test_a_query_that_matches_nothing_still_lists_nothing(client, as_role, fake_mcrit):
    """The guard: prepending an absent id_match must not conjure a row."""
    as_role("visitor")
    fake_mcrit.search_families = lambda *args, **kwargs: {
        "search_results": {}, "cursor": {"forward": None, "backward": None},
        "id_match": None, "sha_match": None,
    }

    response = client.get("/explore/families?query=zzznothing")

    assert response.status_code == 200
    assert row_count(response, "family") == 0


# --- the exact hit belongs on the first page, and only there ---------------------
#
# mcrit computes `id_match` (and `sha_match`) from the search term *before* the
# cursor is applied and attaches the result to every page it answers - see
# `MinHashIndex.getFamilySearchResults` and its two siblings, where the lookup runs
# at the top of the method and the assignment happens after
# `_getSearchResultTemplate` has already windowed the text hits. A view that
# prepends it unconditionally therefore repeats one row, badge and all, on page 2,
# 3, 4 ... and inflates each of those pages past the limit the reader asked for.

#: One of the sizes the `limit` query param accepts. Small enough to page quickly.
PAGE_LIMIT = 10

#: 25 text hits: three pages at PAGE_LIMIT, so there is a middle page as well as a last.
TEXT_HIT_IDS = list(range(100, 125))

#: The record the backend answers as the exact hit. Deliberately not among the text
#: hits, which is the shape mcrit produces for a bare id whose record does not also
#: carry that id in a searchable field.
EXACT_ID = 1


def clone(template, id_field, new_id):
    """A search result dict like the wire carries, under a chosen id."""
    entry = dict(template)
    entry[id_field] = new_id
    return entry


def paged_search(entries, id_field, id_match=None, sha_match=None):
    """A backend that pages the way mcrit's search does, exact hit and all.

    The cursor is an offset rather than mcrit's serialised sort key; the views must
    not read either, and `tests/fixtureData.py` makes the same trade. What this has
    to reproduce is the part the bug lives in: the exact hit is derived from the
    search term, not from the window, so it comes back with *every* page.
    """
    def _search(search_term="", cursor=None, is_ascending=True, sort_by=None, limit=PAGE_LIMIT, *args, **kwargs):
        start = int(cursor) if cursor else 0
        window = entries[start:start + limit]
        return {
            "search_results": {str(entry[id_field]): entry for entry in window},
            "cursor": {
                "forward": str(start + limit) if start + limit < len(entries) else None,
                "backward": str(max(0, start - limit)) if start else None,
            },
            "id_match": id_match,
            "sha_match": sha_match,
        }
    return _search


@contextmanager
def rendered_context(app):
    """The context a page was rendered with - the rows themselves, not their markup."""
    contexts = []

    def record(sender, template, context, **extra):
        contexts.append(context)

    template_rendered.connect(record, app)
    try:
        yield contexts
    finally:
        template_rendered.disconnect(record, app)


def id_of(row, id_field):
    """Rows reach the templates as entry objects on two of the pages and as raw dicts
    on the third; `explore.functions` has always kept them as dicts."""
    return row[id_field] if isinstance(row, dict) else getattr(row, id_field)


def walk_pages(client, app, path, context_key, id_field):
    """Follow the forward cursor across the whole listing, as the "next" link does.

    Returns the ids rendered on each page, in order.
    """
    pages = []
    cursor = None
    page_number = 1
    while True:
        url = f"{path}&page={page_number}&limit={PAGE_LIMIT}"
        if cursor is not None:
            url += f"&cursor={cursor}"
        with rendered_context(app) as contexts:
            response = client.get(url)
        assert response.status_code == 200, f"{url} answered {response.status_code}"
        # flask-dropzone renders a string template of its own first, so pick the
        # context that actually belongs to the listing rather than the first one
        context = next((ctx for ctx in contexts if context_key in ctx), None)
        assert context is not None, f"{url} did not render the listing"
        pages.append([id_of(row, id_field) for row in context[context_key]])
        cursor = context["pagination"].cursor["forward"]
        page_number += 1
        if cursor is None:
            return pages
        assert page_number < 10, "the fake never ran out of pages"


#: name, path, template context key, id field, client method, corpus pool
LISTINGS = [
    ("family", "/explore/families", "families", "family_id", "search_families", "_families"),
    ("sample", "/explore/samples", "samples", "sample_id", "search_samples", "_samples"),
    ("function", "/explore/functions", "functions", "function_id", "search_functions", "_functions"),
]


def stage(fake_mcrit, listing, exact_key="id_match"):
    """Wire the listing up with 25 text hits plus an exact hit that is not among them."""
    _, path, context_key, id_field, method, pool = listing
    corpus = getattr(fake_mcrit, pool)
    template = corpus[sorted(corpus)[0]].toDict()
    entries = [clone(template, id_field, hit_id) for hit_id in TEXT_HIT_IDS]
    exact = clone(template, id_field, EXACT_ID)
    setattr(fake_mcrit, method, paged_search(entries, id_field, **{exact_key: exact}))
    return path, context_key, id_field


@pytest.mark.parametrize("listing", LISTINGS, ids=[entry[0] for entry in LISTINGS])
def test_the_exact_hit_is_listed_once_across_the_whole_paged_listing(client, app, as_role, fake_mcrit, listing):
    """The bug: `id_match` arrives with every page, so it was prepended to every page."""
    as_role("visitor")
    path, context_key, id_field = stage(fake_mcrit, listing)

    pages = walk_pages(client, app, f"{path}?query={EXACT_ID}", context_key, id_field)

    assert len(pages) == 3, f"expected three pages of {PAGE_LIMIT}, got {[len(page) for page in pages]}"
    appearances = [number for number, page in enumerate(pages, 1) if EXACT_ID in page]
    assert appearances == [1], \
        f"the exact hit was listed on pages {appearances}, but belongs to the first page only"


@pytest.mark.parametrize("listing", LISTINGS, ids=[entry[0] for entry in LISTINGS])
def test_no_page_is_inflated_by_the_exact_hit(client, app, as_role, fake_mcrit, listing):
    """Every page carries its full window of text hits, and no page past the first
    carries anything else.

    The exact hit itself is deliberately *not* counted against the limit, so the first
    page may carry PAGE_LIMIT + 1 rows: it is an answer to the query rather than a
    member of the paged result set, and making room for it by dropping a text hit
    would hide that hit for good - mcrit builds the forward cursor from the last entry
    it returned (`_getSearchResultTemplate`), so the next page resumes *after* the
    dropped row. See the note on `explore.exact_matches_to_prepend`.
    """
    as_role("visitor")
    path, context_key, id_field = stage(fake_mcrit, listing)

    pages = walk_pages(client, app, f"{path}?query={EXACT_ID}", context_key, id_field)

    text_hits_seen = []
    for number, page in enumerate(pages, 1):
        text_hits = [row_id for row_id in page if row_id != EXACT_ID]
        text_hits_seen.extend(text_hits)
        assert len(text_hits) <= PAGE_LIMIT, f"page {number} carries {len(text_hits)} of a {PAGE_LIMIT} window"
        expected = PAGE_LIMIT + 1 if number == 1 else PAGE_LIMIT
        assert len(page) <= expected, f"page {number} rendered {len(page)} rows, its limit is {expected}"
    assert text_hits_seen == TEXT_HIT_IDS, "the text hits did not survive paging intact"


def test_a_sample_sha_match_is_not_repeated_on_every_page(client, app, as_role, fake_mcrit):
    """`sha_match` is the samples page's second exact hit and travels the same way."""
    as_role("visitor")
    listing = [entry for entry in LISTINGS if entry[0] == "sample"][0]
    path, context_key, id_field = stage(fake_mcrit, listing, exact_key="sha_match")

    pages = walk_pages(client, app, f"{path}?query={'a' * 64}", context_key, id_field)

    appearances = [number for number, page in enumerate(pages, 1) if EXACT_ID in page]
    assert appearances == [1], f"the sha match was listed on pages {appearances}"


@pytest.mark.parametrize("listing", LISTINGS, ids=[entry[0] for entry in LISTINGS])
def test_paging_is_untouched_when_there_is_no_exact_hit(client, app, as_role, fake_mcrit, listing):
    """The guard on the guard: suppressing the exact hit must not disturb ordinary paging."""
    as_role("visitor")
    _, path, context_key, id_field, method, pool = listing
    corpus = getattr(fake_mcrit, pool)
    template = corpus[sorted(corpus)[0]].toDict()
    entries = [clone(template, id_field, hit_id) for hit_id in TEXT_HIT_IDS]
    setattr(fake_mcrit, method, paged_search(entries, id_field))

    pages = walk_pages(client, app, f"{path}?query=whatever", context_key, id_field)

    assert [len(page) for page in pages] == [PAGE_LIMIT, PAGE_LIMIT, len(TEXT_HIT_IDS) - 2 * PAGE_LIMIT]
    assert [row_id for page in pages for row_id in page] == TEXT_HIT_IDS


if __name__ == "__main__":
    unittest.main()
