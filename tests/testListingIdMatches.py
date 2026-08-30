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

import pytest

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


if __name__ == "__main__":
    unittest.main()
