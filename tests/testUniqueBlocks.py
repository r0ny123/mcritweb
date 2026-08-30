#!/usr/bin/python
"""Unique blocks as a configurable analysis, not only a one-click button - issue #93.

The feature has two halves, and they are configurable in two quite different senses.

*Which samples.* `requestUniqueBlocksForSamples` has always taken a list, but the only
way into it was the cubes button on a single sample row, which passes exactly one id.
`/analyze/unique_blocks` is the selection page the other analysis methods have, and
`/analyze/start_unique_blocks` submits what it selected.

*Which rule.* The six `generateYaraRule` knobs the issue names - `min_ins`, `max_ins`,
`min_bytes`, `max_bytes`, `required_per_sample`, `condition_required` - are not job
parameters at all. The backend stores blocks and statistics; `data.result` builds the
rule out of that cached result on every render. So they reapply to a job that already
ran and there is nothing to resubmit, which is what the issue's third bullet asks for.

That is also the only sense in which the *job* can be configured. Neither
`requestUniqueBlocksForSamples` nor `requestUniqueBlocksForFamily` takes a
`force_recalculation`, so a repeat request for the same samples is answered out of
mcrit's descriptor cache with the job it already has. Which is why the selection is
normalized before submission: `[2, 1]` and `[1, 2]` are the same question, but they
hash to two different descriptors and would run twice.
"""

import copy
import json
import logging
import unittest

import pytest
from fixtureData import job_id_of, load

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

#: The job id the multi-sample variant below is served under. The captured corpus only
#: holds a family job, and a family job is the one shape the result page already handled.
MULTI_SAMPLE_JOB_ID = "6a74660af8b8d2c6f8366400"


# --- the selection page ----------------------------------------------------------

class TestTheSelectionPage:
    """Rendered against the captured corpus, so the sample table holds real entries."""

    @pytest.fixture
    def fake_mcrit(self, corpus_mcrit):
        return corpus_mcrit

    def test_the_page_renders(self, client, as_role):
        as_role("visitor")
        response = client.get("/analyze/unique_blocks")
        assert response.status_code == 200

    def test_the_analyze_menu_offers_it(self, client, as_role):
        """The issue's first complaint: the method produces a job and a result view like
        the other four, and was reachable only from a row button."""
        as_role("visitor")
        response = client.get("/analyze/compare")
        assert b"/analyze/unique_blocks" in response.data

    def test_the_selected_samples_are_listed_back(self, client, as_role):
        as_role("visitor")
        response = client.get("/analyze/unique_blocks?samples=0,1")

        samples = load("samples")
        assert samples["0"]["sha256"][:8].encode() in response.data
        assert samples["1"]["sha256"][:8].encode() in response.data

    def test_the_submit_link_carries_the_whole_selection(self, client, as_role):
        """The point of the page. A selection that reaches the button as one id would
        be the cubes button with extra steps."""
        as_role("visitor")
        response = client.get("/analyze/unique_blocks?samples=0,1,2")
        assert b"[0, 1, 2]" in response.data

    def test_a_sample_that_no_longer_exists_is_dropped_from_the_selection(self, client, as_role):
        as_role("visitor")
        response = client.get("/analyze/unique_blocks?samples=0,9999", follow_redirects=True)

        assert response.status_code == 200
        assert b"9999" in response.data and b"does not exist" in response.data

    def test_a_malformed_sample_list_is_reported_rather_than_raising(self, client, as_role):
        """A hand-typed or truncated URL. `parse_integer_list_query_param` refuses the
        whole value, and the page has to say so instead of rendering an empty selection
        as if nothing had been asked for."""
        as_role("visitor")
        response = client.get("/analyze/unique_blocks?samples=1,,2")

        assert response.status_code == 200
        assert b"not a list of sample ids" in response.data

    def test_an_empty_selection_is_not_an_error(self, client, as_role):
        """Arriving from the menu is the normal case, not a malformed request."""
        as_role("visitor")
        response = client.get("/analyze/unique_blocks?samples=")

        assert response.status_code == 200
        assert b"not a list of sample ids" not in response.data


# --- submitting the selection ----------------------------------------------------

class TestSubmittingTheSelection:
    """Asserts on what reaches the client, since forwarding the selection unchanged
    (and in a stable order) is the whole job of the route."""

    @pytest.fixture
    def fake_mcrit(self, recording_mcrit):
        return recording_mcrit

    def submitted(self, fake):
        calls = [args for name, args, _ in fake.calls if name == "requestUniqueBlocksForSamples"]
        assert calls, "no unique-blocks job was queued"
        return calls

    def test_every_selected_sample_is_submitted_as_one_request(self, client, as_role, fake_mcrit):
        as_role("visitor")
        response = client.get("/analyze/start_unique_blocks?samples=1,2,3")

        assert response.status_code == 302
        assert "/data/jobs/" in response.headers["Location"]
        assert self.submitted(fake_mcrit) == [([1, 2, 3],)]

    def test_the_same_selection_in_another_order_reaches_the_backend_identically(self, client, as_role, fake_mcrit):
        """mcrit hashes the method and its parameters into a descriptor and answers a
        repeat from the job it already has. The list is part of that hash, so an
        unordered selection would run the same analysis twice."""
        as_role("visitor")
        client.get("/analyze/start_unique_blocks?samples=3,1,2")
        client.get("/analyze/start_unique_blocks?samples=1,2,3")

        first, second = self.submitted(fake_mcrit)
        assert first == second == ([1, 2, 3],)

    def test_a_sample_selected_twice_is_submitted_once(self, client, as_role, fake_mcrit):
        as_role("visitor")
        client.get("/analyze/start_unique_blocks?samples=2,1,2")
        assert self.submitted(fake_mcrit) == [([1, 2],)]

    def test_the_request_never_forces_a_recalculation(self, client, as_role, fake_mcrit):
        """There is no such parameter on either unique-blocks method. Pinned so that
        passing one becomes a deliberate act rather than a silent TypeError."""
        as_role("visitor")
        client.get("/analyze/start_unique_blocks?samples=1")

        _name, _args, kwargs = next(call for call in fake_mcrit.calls if call[0] == "requestUniqueBlocksForSamples")
        assert kwargs == {}

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            ("", b"select at least one sample"),
            ("?samples=", b"select at least one sample"),
            ("?samples=abc", b"not a list of sample ids"),
            ("?samples=,1", b"not a list of sample ids"),
            ("?samples=1,", b"not a list of sample ids"),
            ("?samples=-1", b"not a list of sample ids"),
        ],
    )
    def test_a_selection_that_cannot_be_used_is_reported_not_submitted(self, client, as_role, fake_mcrit, query, expected):
        as_role("visitor")
        response = client.get(f"/analyze/start_unique_blocks{query}", follow_redirects=True)

        assert response.status_code == 200
        assert expected in response.data
        assert not [call for call in fake_mcrit.calls if call[0] == "requestUniqueBlocksForSamples"]

    def test_more_samples_than_one_request_can_carry_are_refused(self, client, as_role, fake_mcrit):
        """The list goes into the request *path* the client builds, so an unbounded
        selection is a request line the mcrit server rejects, not a slow query."""
        from mcritweb.views.analyze import MAX_SELECTED_SAMPLES

        as_role("visitor")
        oversized = ",".join(str(i) for i in range(MAX_SELECTED_SAMPLES + 1))
        response = client.get(f"/analyze/start_unique_blocks?samples={oversized}", follow_redirects=True)

        assert response.status_code == 200
        assert str(MAX_SELECTED_SAMPLES).encode() in response.data
        assert not [call for call in fake_mcrit.calls if call[0] == "requestUniqueBlocksForSamples"]

    def test_exactly_the_maximum_is_still_submitted(self, client, as_role, fake_mcrit):
        """The other side of the boundary - an off-by-one here silently costs a sample."""
        from mcritweb.views.analyze import MAX_SELECTED_SAMPLES

        as_role("visitor")
        largest = ",".join(str(i) for i in range(MAX_SELECTED_SAMPLES))
        client.get(f"/analyze/start_unique_blocks?samples={largest}")

        assert self.submitted(fake_mcrit) == [(list(range(MAX_SELECTED_SAMPLES)),)]


class TestABackendThatDoesNotAnswerAJobId:
    """`requestUniqueBlocksForSamples` returns whatever `handle_response` made of the
    reply, which is None for a 4xx or a 500. Building the redirect from that raises in
    url_for, so the route has to notice before it gets there."""

    @pytest.fixture
    def fake_mcrit(self, recording_mcrit):
        recording_mcrit.requestUniqueBlocksForSamples = lambda *args, **kwargs: None
        return recording_mcrit

    def test_it_is_reported_rather_than_raising(self, client, as_role):
        as_role("visitor")
        response = client.get("/analyze/start_unique_blocks?samples=1,2", follow_redirects=True)

        assert response.status_code == 200
        assert b"did not accept" in response.data


# --- rule parameters, reapplied to a job that already ran ------------------------

class TestRuleParametersOnTheResultPage:

    @pytest.fixture
    def fake_mcrit(self, corpus_mcrit):
        return corpus_mcrit

    @pytest.fixture
    def result_url(self, client, as_role):
        """The report URL, with `data.result`'s local cache already warm.

        Not a convenience. The first render of a report serves it straight from the
        backend and writes it to instance/cache/results; every later one reads it back.
        `cache_result` writes through `flask.json`, whose provider sorts keys, and
        `generateBlockCover` breaks ties between equally valuable blocks by the order it
        met them - so a first render and a second render of the same URL produce two
        different, equally valid rules. That is pre-existing and has nothing to do with
        the parameters, but comparing one render against another across that boundary
        would make these tests pass for the wrong reason.
        """
        as_role("visitor")
        url = f"/data/result/{job_id_of('unique_blocks')}"
        client.get(url)
        return url

    def rule_of(self, response):
        """The rule as rendered, without the surrounding page."""
        body = response.data.decode()
        start = body.index("rule mcrit_")
        return body[start:body.index("</textarea>", start)]

    def test_the_defaults_reproduce_the_rule_the_backend_stored(self, client, as_role, result_url):
        """The knobs are applied here rather than by the worker, so an unparameterized
        render has to land on the same cover the stored statistics describe - otherwise
        every existing result page would quietly change meaning."""
        response = client.get(result_url)

        statistics = load("unique_blocks.result")["statistics"]
        assert response.status_code == 200
        assert f"covering {statistics['num_samples_covered']}/{statistics['num_samples']}".encode() in response.data

    def test_a_parameter_rebuilds_the_rule_without_queueing_anything(self, client, as_role, fake_mcrit, result_url):
        """The issue's third bullet: rule generation happens at render time from a
        cached result, so a different rule costs a render, not a job."""
        default = client.get(result_url)
        narrowed = client.get(f"{result_url}?condition_required=3")

        assert self.rule_of(default) != self.rule_of(narrowed)
        assert "3 of them" in self.rule_of(narrowed)
        assert not [call for call in fake_mcrit.calls if call[0].startswith("requestUnique")]

    def test_an_instruction_bound_changes_which_blocks_are_selected(self, client, as_role, result_url):
        default = client.get(result_url)
        bounded = client.get(f"{result_url}?min_ins=30")

        assert self.rule_of(default) != self.rule_of(bounded)

    def test_a_byte_bound_changes_which_blocks_are_selected(self, client, as_role, result_url):
        default = client.get(result_url)
        bounded = client.get(f"{result_url}?min_bytes=64")

        assert self.rule_of(default) != self.rule_of(bounded)

    def test_the_reported_coverage_follows_the_parameters(self, client, as_role, result_url):
        """The page's "has a YARA rule / covers n samples" lines describe the rule shown
        below them. Reading them off the stored statistics would keep claiming a
        complete cover for parameters that produced no rule at all."""
        response = client.get(f"{result_url}?max_ins=1")

        assert response.status_code == 200
        assert b"True, covers: 3 samples" not in response.data

    def test_parameters_that_select_nothing_do_not_lock_away_the_form(self, client, as_role, result_url):
        """The tab is disabled when the report has no rule to offer. Keying that on the
        recomputed cover instead would disable it the moment a bound selected no blocks,
        taking the only control that could undo the bound away with it."""
        response = client.get(f"{result_url}?max_ins=1&tab=yara")

        body = response.data.decode()
        tab = body[body.index('id="pills-yara-tab"') - 200:body.index('id="pills-yara-tab"')]
        assert "disabled" not in tab
        assert 'name="max_ins"' in body
        assert "selected no blocks" in body

    def test_the_blocks_per_sample_is_bounded(self, client, as_role, result_url):
        """The one knob that costs time rather than only changing the answer.
        generateBlockCover selects one block per pass and rescans the rest, so this is
        the k in an O(k*n) walk: on a 6124-block report the default 10 costs 0.08s, 1000
        costs 24s. Left unbounded it is a long-running request any visitor can ask for."""
        from mcritweb.views.data import YARA_REQUIRED_PER_SAMPLE_MAXIMUM

        capped = client.get(f"{result_url}?required_per_sample=100000&tab=yara")
        at_the_cap = client.get(f"{result_url}?required_per_sample={YARA_REQUIRED_PER_SAMPLE_MAXIMUM}&tab=yara")

        assert self.rule_of(capped) == self.rule_of(at_the_cap)
        assert f'name="required_per_sample" value="{YARA_REQUIRED_PER_SAMPLE_MAXIMUM}"'.encode() in capped.data

    def test_a_bound_below_the_cap_is_left_alone(self, client, as_role, result_url):
        """The other side of it - clamping everything to the cap would be a cap of one."""
        response = client.get(f"{result_url}?required_per_sample=2&tab=yara")

        assert b'name="required_per_sample" value="2"' in response.data

    def test_the_rule_parameters_survive_the_block_filter_in_both_directions(self, client, as_role, result_url):
        """The block filter form carries the rule parameters; this is the other form,
        which has to carry the block filter back or filtering is undone by regenerating."""
        response = client.get(f"{result_url}?min_score=50&tab=yara")

        assert b'name="min_score" value="50"' in response.data

    @pytest.mark.parametrize("query", ["condition_required=-5", "condition_required=0"])
    def test_a_condition_below_one_is_clamped(self, client, as_role, result_url, query):
        """"0 of them" matches nothing and "-5 of them" does not compile, and the rule
        is offered for copying straight into YARA."""
        response = client.get(f"{result_url}?{query}")

        rule = self.rule_of(response)
        assert "1 of them" in rule
        assert "-5 of them" not in rule and "0 of them" not in rule

    @pytest.mark.parametrize(
        "query",
        ["min_ins=-4", "max_ins=-4", "min_bytes=-4", "max_bytes=-4", "required_per_sample=-4",
         "min_ins=notanumber", "min_ins=", "min_ins=0x10", "required_per_sample=0"],
    )
    def test_a_parameter_the_ui_would_not_send_still_renders(self, client, as_role, result_url, query):
        response = client.get(f"{result_url}?{query}")
        assert response.status_code == 200

    def test_the_parameters_survive_the_block_filter_form(self, client, as_role, result_url):
        """Two GET forms on one page. Either one dropping the other's parameters means
        a tuned rule is lost the moment the block list is filtered."""
        response = client.get(f"{result_url}?condition_required=3&tab=blocks")

        assert b'name="condition_required" value="3"' in response.data


# --- the result page for a multi-sample job --------------------------------------

class TestAMultiSampleResult:
    """The captured job is a family job, and the sample-set job is what this feature
    newly makes reachable. The page named a single sample in its heading and looked up
    only `sample_ids[0]`, which for a five-sample request is simply the wrong answer."""

    @pytest.fixture
    def fake_mcrit(self, corpus_mcrit):
        job, result = copy.deepcopy(corpus_mcrit._jobs[job_id_of("unique_blocks")])
        job["_id"]["$oid"] = MULTI_SAMPLE_JOB_ID
        # what requestUniqueBlocksForSamples produces: positional argument 0 only, no
        # family_id - see mcrit's BlocksResource.on_get_unique_blocks_for_samples
        job["payload"]["params"] = json.dumps({"0": [0, 1, 2]})
        job["payload"]["descriptor"] = json.dumps(["getUniqueBlocks", {"0": [0, 1, 2]}, {}])
        corpus_mcrit._jobs[MULTI_SAMPLE_JOB_ID] = (job, result)
        return corpus_mcrit

    def test_the_page_renders(self, client, as_role):
        as_role("visitor")
        response = client.get(f"/data/result/{MULTI_SAMPLE_JOB_ID}")
        assert response.status_code == 200
        assert b"are corrupted" not in response.data

    def test_it_names_every_sample_in_the_request(self, client, as_role):
        """Asserted on the row that reports the request, not on the page as a whole: the
        per-sample statistics table links the same ids, so a page-wide search passes
        whether or not the request itself is reported at all."""
        as_role("visitor")
        response = client.get(f"/data/result/{MULTI_SAMPLE_JOB_ID}")

        body = response.data.decode()
        row = body[body.index("Requested Samples"):]
        row = row[:row.index("</tr>")]
        for sample_id in (0, 1, 2):
            assert f'/explore/samples/{sample_id}"' in row

    def test_it_does_not_present_a_sample_set_as_a_single_sample(self, client, as_role):
        as_role("visitor")
        response = client.get(f"/data/result/{MULTI_SAMPLE_JOB_ID}")
        assert b"Unique Blocks for Sample: 0" not in response.data


if __name__ == "__main__":
    unittest.main()
