#!/usr/bin/python
"""What the explore pages ask the backend for, and what they still show for it.

Issue #77 is "searching for samples is slow". Two of the three backend calls behind
`/explore/samples` have nothing to do with the query: the view downloaded the whole
job queue to annotate at most 25 rows, and the whole family table to fill a
type-ahead in a modal nobody had opened. A queue and a family table both grow
monotonically with instance use, so both cost more on exactly the instances where
the complaint comes from.

Issue #76 is the neighbouring one: `/explore/search` fans out to all three
collections, and the function search is the slow one - ~30 seconds on a large
database, worst when it finds nothing. That cost is mcrit's to fix; what is fixable
here is who is charged for it.

These tests are call counts, and they are paired deliberately with assertions on what
the page still renders. Narrowing a fetch is only a fix while the annotation it fed
survives - a listing that quietly stops showing which samples have matching jobs is a
regression, not an improvement, and a search that quietly stops looking at functions
is one too.
"""

import logging
import re

import pytest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

#: `sample_row` renders this when a sample has matching jobs, with the count after it.
JOB_BADGE = re.compile(r'id="sample_(-?\d+)_analyze".*?</button>', re.DOTALL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


def calls_to(fake_mcrit, name):
    return [(args, kwargs) for called, args, kwargs in fake_mcrit.calls if called == name]


def badges(response):
    """sample_id -> the number in its job badge, for every row that has one."""
    found = {}
    for match in JOB_BADGE.finditer(response.get_data(as_text=True)):
        if "color:green" in match.group(0):
            found[int(match.group(1))] = int(re.search(r"&nbsp;(\d+)", match.group(0)).group(1))
    return found


# --- the queue is fetched by method, not wholesale --------------------------------

@pytest.mark.parametrize("path", ["/explore/samples", "/explore/samples?query=citadel"])
def test_a_listing_asks_the_queue_only_for_the_methods_its_rows_can_show(client, as_role, fake_mcrit, path):
    """An unqualified `getQueueData()` is the whole queue: `McritClient` omits `limit`
    from the query string when it is 0, and mcrit reads a missing limit as "all". The
    two methods named here are the only ones `sample_row` can reach - `has_sample_id`
    answers for nothing else - so the rest was fetched and dropped."""
    as_role("visitor")
    fake_mcrit.calls.clear()

    client.get(path)

    methods = sorted(kwargs.get("method") for _args, kwargs in calls_to(fake_mcrit, "getQueueData"))
    assert methods == ["getMatchesForSample", "getMatchesForSampleVs"], (
        f"{path} asked the queue for {methods}"
    )


def test_a_listing_with_no_rows_asks_the_queue_for_nothing(client, as_role, fake_mcrit):
    """`/explore/families/1` is the example because the offline fake makes it one: it
    models search as a substring match, not mcrit's `field:value` parser, so the
    `family_id:1` query the view builds matches no sample. A page with no rows has
    nothing to annotate either way."""
    as_role("visitor")
    fake_mcrit.calls.clear()

    response = client.get("/explore/families/1")

    assert response.status_code == 200
    assert calls_to(fake_mcrit, "getQueueData") == []


def test_the_listing_still_shows_which_samples_have_matching_jobs(client, as_role, fake_mcrit):
    """The counterweight to the test above. The captured queue holds one
    `getMatchesForSample(0)` and one `getMatchesForSampleVs(1, 3)`, and the second one
    annotates both of its samples - `has_sample_id` looks at both arguments."""
    as_role("visitor")

    response = client.get("/explore/samples")

    assert badges(response) == {0: 1, 1: 1, 3: 1}


def test_the_listing_still_links_the_last_matching_job(client, as_role, fake_mcrit):
    """The dropdown's "Last 1:N Job" is the other thing the queue feeds. It takes the
    first entry of the filtered list, so the newest-first order the backend answers in
    is load-bearing - fetching per method must not reorder it."""
    as_role("visitor")
    job_id = next(
        job["_id"]["$oid"] for job in fake_mcrit._queue
        if job["payload"]["method"] == "getMatchesForSample"
    )

    response = client.get("/explore/samples")

    assert f"/data/result/{job_id}" in response.get_data(as_text=True)


def test_a_failed_queue_read_costs_the_annotations_not_the_page(client, as_role, fake_mcrit):
    """`McritClient` answers None when the backend errors, and `JobCollection(None)`
    used to take the request down with a TypeError. The rows are the page; the job
    badges are decoration on them."""
    as_role("visitor")
    fake_mcrit.getQueueData = lambda *args, **kwargs: None

    response = client.get("/explore/samples")

    assert response.status_code == 200
    assert badges(response) == {}
    assert "job queue failed" in response.get_data(as_text=True)


# --- the single sample page narrows by sample id ----------------------------------

def test_the_single_sample_page_forwards_its_sample_id_as_a_filter(client, as_role, fake_mcrit):
    """`filter=sample_id` was passed as an int, and `McritClient.getQueueData` forwards
    a `filter` only when `isinstance(filter, str)` - so the argument was dropped and
    the whole queue came back anyway."""
    as_role("visitor")
    fake_mcrit.calls.clear()

    client.get("/explore/samples/0")

    assert [kwargs.get("filter") for _args, kwargs in calls_to(fake_mcrit, "getQueueData")] == ["0"]


def test_the_single_sample_page_still_lists_every_job_of_the_sample(client, as_role, fake_mcrit):
    """mcrit matches `filter` as a substring of the job's `method(args...)` string,
    which is a superset of the jobs whose own `sample_id` is this one - `Job.sample_id`
    is read from those very arguments - so `filterToSampleIds` still lands exactly."""
    as_role("visitor")

    page = client.get("/explore/samples/0").get_data(as_text=True)

    assert "Sample has <a href=\"#jobs\">2 Jobs" in page
    for job in fake_mcrit._queue:
        if job["payload"]["method"] in ("getMatchesForSample", "getUniqueBlocks"):
            assert job["_id"]["$oid"] in page, f"{job['payload']['method']} vanished from the job table"


def test_the_single_sample_page_survives_a_failed_function_search(client, as_role, fake_mcrit):
    """The job table is read outside the branch that fills it, so a failed function
    search reached an unbound `job_collection` - a 500 on the page whose job it was to
    report the failure. Pre-existing; fixed while narrowing the fetch around it."""
    as_role("visitor")
    fake_mcrit.search_functions = lambda *args, **kwargs: None

    response = client.get("/explore/samples/0")

    assert response.status_code == 200
    assert "failed" in response.get_data(as_text=True)


def test_the_single_sample_page_survives_a_failed_queue_read(client, as_role, fake_mcrit):
    """`JobCollection(None)` is a TypeError one attribute access later."""
    as_role("visitor")
    fake_mcrit.getQueueData = lambda *args, **kwargs: None

    response = client.get("/explore/samples/0")

    assert response.status_code == 200
    assert "job queue failed" in response.get_data(as_text=True)


# --- the fake's fidelity, which the tests above rest on ---------------------------

def test_the_fake_applies_the_queue_filter_after_paging_like_mcrit_does(corpus_mcrit):
    """`QueueRemoteCalls.getQueueData` filters the *already paged* slice, so a `filter`
    combined with a `limit` silently returns fewer rows than the limit asked for
    instead of the first `limit` matches. Nothing may lean on `filter` for paging, and
    the fake has to make that visible rather than hide it."""
    unpaged = corpus_mcrit.getQueueData(filter="addBinarySample")
    paged = corpus_mcrit.getQueueData(filter="addBinarySample", limit=5)

    assert len(unpaged) == 7
    assert paged == [], "the fake paged the matches instead of matching the page"


# --- the family type-ahead is fetched, not embedded -------------------------------

@pytest.mark.parametrize("path", ["/explore/families", "/explore/samples", "/explore/families/1", "/explore/samples/0"])
def test_a_page_with_an_edit_modal_does_not_download_every_family(client, as_role, fake_mcrit, path):
    """`getFamilies()` is one storage lookup per family on mcrit's side
    (`MinHashIndex.getFamilies` walks `getFamilyIds()` calling `getFamily`), and these
    pages made that call to fill a type-ahead in a modal that is usually never opened."""
    as_role("visitor")
    fake_mcrit.calls.clear()

    response = client.get(path)

    assert response.status_code == 200
    assert calls_to(fake_mcrit, "getFamilies") == [], f"{path} still downloads every family"


def test_the_type_ahead_answers_a_bounded_number_of_names(client, as_role, fake_mcrit):
    as_role("visitor")

    response = client.get("/explore/familyNames?q=cit")

    assert response.status_code == 200
    assert response.json == {"family_names": ["win.citadel"]}
    assert [kwargs.get("limit") for _args, kwargs in calls_to(fake_mcrit, "search_families")] == [10]


def test_the_type_ahead_survives_a_backend_that_cannot_answer(client, as_role, fake_mcrit):
    """`search_families` answers None when the backend errors. The field it feeds is a
    free-text input, so the modal is still usable without suggestions."""
    as_role("visitor")
    fake_mcrit.search_families = lambda *args, **kwargs: None

    response = client.get("/explore/familyNames?q=cit")

    assert response.status_code == 200
    assert response.json == {"family_names": []}


# --- the unified search does not run the slow collection unasked ------------------

def test_an_unqualified_search_leaves_the_function_scan_alone(client, as_role, fake_mcrit):
    """Issue #76. This is also what every pagination click on the family or sample
    table used to re-run."""
    as_role("visitor")
    fake_mcrit.calls.clear()

    client.get("/explore/search?query=citadel")

    searched = sorted(name for name, _args, _kwargs in fake_mcrit.calls if name.startswith("search_"))
    assert searched == ["search_families", "search_samples"]


def test_an_unqualified_search_says_that_it_skipped_the_functions(client, as_role, fake_mcrit):
    """The omission must not read as "there are no such functions". The offered link
    has to carry the collections already searched, or taking it would drop them."""
    as_role("visitor")

    page = client.get("/explore/search?query=citadel").get_data(as_text=True)

    assert "Search functions too" in page
    assert "type=family,sample,function" in page


def test_asking_for_functions_still_searches_them(client, as_role, fake_mcrit):
    as_role("visitor")
    fake_mcrit.calls.clear()

    client.get("/explore/search?query=citadel&type=family,sample,function")

    searched = sorted(name for name, _args, _kwargs in fake_mcrit.calls if name.startswith("search_"))
    assert searched == ["search_families", "search_functions", "search_samples"]
