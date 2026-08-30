#!/usr/bin/python
"""The match diagram is rendered by the route that serves it, not by the result page.

Rendering it inline in `data.result_matches_for_sample_or_query`, before
render_template, was the single largest cost of the first view of a result page -
a full PIL render plus a `getFunctionsBySampleId` round trip, in front of HTML the
diagram is not part of. It has had its own route and its own <img> request all
along, so the work belongs there. See issue #68.

What these tests hold onto: the page must no longer pay for it, the image route
must produce the same picture on demand, and every way the render can fail must end
in a missing image rather than in a 500 or a half-written file that gets served.
"""

import io
import logging
import os
import unittest

import pytest
from fixtureData import job_id_of
from mcrit.storage.MatchingResult import MatchingResult

from mcritweb.views.data import DIAGRAM_FILENAME_RE
from mcritweb.views.MatchReportRenderer import MatchReportRenderer

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


def diagrams_dir(app):
    return os.sep.join([app.instance_path, "cache", "diagrams"])


def cached_diagrams(app):
    return sorted(os.listdir(diagrams_dir(app)))


# --- the page no longer renders it ------------------------------------------------

@pytest.mark.parametrize("query", ["", "?famid=1", "?samid=1", "?funid=0"])
def test_result_page_does_not_render_the_diagram(client, as_role, app, corpus_mcrit, query):
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('matches_for_sample')}{query}")

    assert response.status_code == 200
    assert cached_diagrams(app) == [], "the page rendered a diagram it does not serve"
    called = [name for name, _args, _kwargs in corpus_mcrit.calls]
    assert "getFunctionsBySampleId" not in called, "the renderer's backend call is still on the page path"


def test_result_page_still_points_at_the_diagram(client, as_role):
    """The <img> has to keep naming the file the route knows how to build."""
    as_role("visitor")
    job_id = job_id_of("matches_for_sample")
    response = client.get(f"/data/result/{job_id}")

    assert f"/data/diagrams/{job_id}.png".encode() in response.data


# --- the route renders it ---------------------------------------------------------

@pytest.mark.parametrize(
    "report, suffix",
    [
        ("matches_for_sample", ""),
        ("matches_for_sample", "-famid_1"),
        ("matches_for_sample", "-samid_1"),
        ("matches_for_sample", "-funid_0"),
        ("matches_for_sample_vs", ""),
        ("matches_for_query", ""),
    ],
)
def test_diagram_route_renders_on_demand(client, as_role, app, report, suffix):
    """Every name a result template can ask for, plus one it cannot: the 1-vs-1 page
    shows no diagram, so nothing links to `<vs job>.png`. The route draws it anyway
    if it is asked for by hand, which is the one thing it does that the old inline
    rendering did not - a diagram no page displays, for a report it can be drawn
    from. Recorded here rather than special-cased: telling that job kind apart needs
    the job record, which the report itself does not carry.
    """
    as_role("visitor")
    filename = f"{job_id_of(report)}{suffix}.png"
    response = client.get(f"/data/diagrams/{filename}")

    assert response.status_code == 200
    assert response.data.startswith(PNG_MAGIC)
    assert cached_diagrams(app) == [filename], "the render was not cached under the name it was asked for"


def test_diagram_route_serves_the_cached_file_without_re_rendering(client, as_role, app, corpus_mcrit):
    as_role("visitor")
    filename = f"{job_id_of('matches_for_sample')}.png"
    first = client.get(f"/data/diagrams/{filename}")
    corpus_mcrit.calls.clear()
    second = client.get(f"/data/diagrams/{filename}")

    assert first.data == second.data
    assert corpus_mcrit.calls == [], "a cached diagram still went to the backend"


def test_diagram_route_does_not_need_the_result_cache(client, as_role, app):
    """Nothing guarantees the page was visited first, so the route has to be able to
    fetch the report itself."""
    as_role("visitor")
    results_dir = os.sep.join([app.instance_path, "cache", "results"])
    assert os.listdir(results_dir) == []

    response = client.get(f"/data/diagrams/{job_id_of('matches_for_sample')}.png")

    assert response.status_code == 200
    assert response.data.startswith(PNG_MAGIC)


# --- the picture is the one the page used to render -------------------------------

DEFAULT_FILTER_VALUES = {
    "filter_direct_min_score": None,
    "filter_direct_nonlib_min_score": None,
    "filter_frequency_min_score": None,
    "filter_frequency_nonlib_min_score": None,
    "filter_unique_only": None,
    "filter_exclude_own_family": None,
    "filter_family_name": None,
    "filter_function_min_score": None,
    "filter_function_max_score": None,
    "filter_function_offset": None,
    "filter_max_num_families": None,
    "filter_min_num_samples": None,
    "filter_max_num_samples": None,
    "filter_exclude_library": None,
    "filter_exclude_pic": None,
    "filter_func_unique": None,
}


def render_to_bytes(matching_result, **filters):
    renderer = MatchReportRenderer()
    renderer.processReport(matching_result)
    buffer = io.BytesIO()
    renderer.renderStackedDiagram(**filters).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    "filters, narrow",
    [
        ({}, lambda result: None),
        ({"filtered_family_id": 1}, lambda result: result.filterToFamilyId(1)),
        ({"filtered_sample_id": 1}, lambda result: result.filterToSampleId(1)),
        ({"filtered_function_id": 0}, lambda result: None),
    ],
)
def test_the_diagram_does_not_depend_on_the_filtering_the_page_applies(app, corpus_mcrit, filters, narrow):
    """Why the route may re-read the report instead of being handed the page's copy.

    The page narrows a MatchingResult - user filter defaults, then filterToFamilyId
    or filterToSampleId - before it used to render. The renderer reads only the
    unfiltered `function_matches`, `library_matches` and `reference_sample_entry`,
    so both produce the same image. If a future mcrit makes the renderer look at
    the filtered lists, this is where that shows up.
    """
    report = corpus_mcrit.getResultForJob(job_id_of("matches_for_sample"))
    with app.test_request_context("/"):
        as_the_page_had_it = MatchingResult.fromDict(report)
        as_the_page_had_it.setFilterValues(dict(DEFAULT_FILTER_VALUES))
        as_the_page_had_it.getUniqueFamilyMatchInfoForSample(None)
        as_the_page_had_it.applyFilterValues()
        narrow(as_the_page_had_it)

        assert render_to_bytes(as_the_page_had_it, **filters) == render_to_bytes(MatchingResult.fromDict(report), **filters)


# --- everything that can go wrong -------------------------------------------------

@pytest.mark.parametrize(
    "filename",
    [
        "ffffffffffffffffffffffff.png",                       # no such job
        "6a74660af8b8d2c6f83664f1-famid_notanumber.png",      # not a filter we emit
        "not a diagram.png",
        "../results/anything.json",
        "%2e%2e/results/anything.json",
        "*.png",                                              # glob syntax, if it ever reached one
        "[a-z].png",
    ],
)
def test_a_diagram_nobody_can_render_is_a_404_not_a_500(client, as_role, app, filename):
    as_role("visitor")
    response = client.get(f"/data/diagrams/{filename}")

    assert response.status_code in (301, 400, 404), response.status_code
    assert cached_diagrams(app) == [], "a failed render left a file behind"


@pytest.mark.parametrize("suffix", ["-famid_9999", "-samid_9999", "-funid_9999"])
def test_a_filter_the_page_would_have_rejected_draws_nothing(client, as_role, app, suffix):
    """The page checked isFamilyId / isSampleId, and looked a function id up in the
    report, before it linked to a diagram. A URL typed by hand reaches the renderer
    directly, so the route has to check the same things - or the cache fills with
    diagrams of families and samples that do not exist."""
    as_role("visitor")
    response = client.get(f"/data/diagrams/{job_id_of('matches_for_sample')}{suffix}.png")

    assert response.status_code == 404
    assert cached_diagrams(app) == []


@pytest.mark.parametrize("report", ["cross_compare", "unique_blocks"])
def test_a_job_that_is_not_a_match_report_does_not_render_a_diagram(client, as_role, app, report):
    """`/data/diagrams/<job_id>.png` takes any job id, and only some jobs carry a
    report a diagram can be drawn from."""
    as_role("visitor")
    response = client.get(f"/data/diagrams/{job_id_of(report)}.png")

    assert response.status_code == 404
    assert cached_diagrams(app) == [], "a failed render left a file behind"


def test_a_query_report_has_no_function_filtered_diagram(client, as_role, app):
    """A query's functions are not in the corpus, so there is nothing to lay a
    function-filtered diagram out over - as before, none is produced."""
    as_role("visitor")
    response = client.get(f"/data/diagrams/{job_id_of('matches_for_query')}-funid_-1.png")

    assert response.status_code == 404
    assert cached_diagrams(app) == []


def test_a_broken_render_leaves_no_partial_file(client, as_role, app, monkeypatch):
    """The diagram is written to a temporary file and renamed, so a render that dies
    half way through cannot leave something that later looks like a cached diagram."""
    as_role("visitor")

    def explode(*args, **kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(MatchReportRenderer, "renderStackedDiagram", explode)
    response = client.get(f"/data/diagrams/{job_id_of('matches_for_sample')}.png")

    assert response.status_code == 404
    assert cached_diagrams(app) == []


# --- the filename grammar ---------------------------------------------------------

@pytest.mark.parametrize(
    "filename, expected",
    [
        ("6a74660af8b8d2c6f83664f1.png", ("6a74660af8b8d2c6f83664f1", None, None)),
        ("6a74660af8b8d2c6f83664f1-famid_7.png", ("6a74660af8b8d2c6f83664f1", "famid", "7")),
        ("6a74660af8b8d2c6f83664f1-samid_0.png", ("6a74660af8b8d2c6f83664f1", "samid", "0")),
        ("6a74660af8b8d2c6f83664f1-funid_-3.png", ("6a74660af8b8d2c6f83664f1", "funid", "-3")),
        # a local queue hands out uuid4 job ids, which contain the same dash the
        # filter suffix is joined with - the id must not swallow the suffix
        ("2f1a9b04-1f6d-4a1e-9a1c-0c5f2f9b8e77.png", ("2f1a9b04-1f6d-4a1e-9a1c-0c5f2f9b8e77", None, None)),
        ("2f1a9b04-1f6d-4a1e-9a1c-0c5f2f9b8e77-famid_7.png",
         ("2f1a9b04-1f6d-4a1e-9a1c-0c5f2f9b8e77", "famid", "7")),
    ],
)
def test_diagram_filenames_are_parsed_back_into_their_parts(filename, expected):
    match = DIAGRAM_FILENAME_RE.match(filename)
    assert match is not None
    assert (match.group("job_id"), match.group("filter_kind"), match.group("filter_id")) == expected


@pytest.mark.parametrize(
    "filename",
    [
        "../secrets.png",
        "sub/dir.png",
        "job.id.png",
        "job id.png",
        "*.png",
        "job.jpg",
        ".png",
        "6a74660af8b8d2c6f83664f1-famid_7.png.png",
        "a" * 65 + ".png",
    ],
)
def test_a_filename_the_app_never_wrote_is_not_parsed(filename):
    assert DIAGRAM_FILENAME_RE.match(filename) is None


if __name__ == "__main__":
    unittest.main()
