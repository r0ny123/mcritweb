#!/usr/bin/python
"""Renders every result type against real reports from tests/fixtures/.

Until now nothing here rendered a result page: the strict fake answers with empty
shapes, which proves a route is reachable and nothing about whether the template can
survive the data. These tests run the real dispatch in `data.result()` over captured
reports, so a template that dereferences a field the backend stopped sending, or a
renderer that miscounts a filtered report, fails here rather than in a browser.

The reports come from a live instance - see tests/fixtures/regenerate.py.
"""

import collections
import html
import logging
import re
import unittest

import pytest
from fixtureData import job_id_of

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


#: `<script>...</script>` as it comes off the rendered page. Used to lint the block
#: that defines the clipboard helper, so an unrelated script is never the offender.
SCRIPT_BLOCK = re.compile(r"<script\b[^>]*>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)

#: The copy icon and the textarea it copies, tied together: a helper wired to the
#: wrong id is as broken as no helper.
COPY_ICON = re.compile(r"<i\b[^>]*onclick=\"copyTextAreaToClipboard\('#yara_text'\)\"")

#: `// ...` to end of line. The helper's own comment names the old implementation on
#: purpose, so the lint below reads the code with the comments taken out.
LINE_COMMENT = re.compile(r"//[^\n]*")

#: The shapes of the pre-#80 helper. It filled a detached textarea from
#: `$(element).html()`, so what reached the clipboard was the rendered *markup*:
#: HTML-escaped, and frozen at page load however the reader had edited the rule.
COPIES_THE_MARKUP = ("copyElementToClipboard", ".html()", ".innerHTML")


#: The Block column of the unique blocks table: a `/* ... */` comment and then the
#: hex sequence in braces, which is what a reader copies into a YARA file.
BLOCK_CELL = re.compile(r"<code style=\"white-space:pre\">(.*?)</code>", re.DOTALL)

#: One byte of a YARA hex string: a pair of hex digits, or `??` for a wildcarded
#: one. Anything else - an odd-length run, most of all - is a syntax error.
HEX_TOKEN = re.compile(r"^(?:[0-9a-f]{2}|\?\?)+$")

#: The rule's comment above each selected picblock, as `renderRule` writes it once
#: `name_functions_in_rule` has been over it.
RULE_PICBLOCK_COMMENT = re.compile(r"/\* picblockhash: (0x[0-9a-f]+) - coverage: \d+/\d+ samples(?P<tail>[^\n]*)")


def statistics_table_of(page):
    """The markup of the "Block Statistics across Samples" table."""
    assert "Block Statistics across Samples" in page, "the statistics table is not on the page"
    return page.split("Block Statistics across Samples")[1].split("</table>")[0]


def hex_sequences_of(page):
    """The `{ ... }` half of every Block cell on the page, unescaped."""
    sequences = []
    for cell in BLOCK_CELL.findall(page):
        _, brace, sequence = html.unescape(cell).partition("{")
        assert brace, "a Block cell carries no hex sequence"
        sequences.append(sequence.rsplit("}", 1)[0])
    return sequences


@pytest.mark.parametrize(
    "report",
    ["matches_for_sample", "matches_for_sample_vs", "matches_for_query", "cross_compare", "unique_blocks"],
)
def test_result_page_renders(client, as_role, report):
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of(report)}")
    assert response.status_code == 200, f"{report} did not render"
    # the h1 of result_corrupted.html - the template's *name* appears nowhere in the
    # rendered page, so asserting on that passed whatever the page actually said
    assert b"are corrupted" not in response.data


@pytest.mark.parametrize("report", ["matches_for_sample", "matches_for_sample_vs", "matches_for_query"])
def test_linkhunt_renders_for_every_matching_report(client, as_role, report):
    as_role("visitor")
    response = client.get(f"/data/linkhunt/{job_id_of(report)}")
    assert response.status_code == 200


def test_result_page_applies_a_score_filter(client, as_role):
    """The filter parameters drive MatchingResult.applyFilterValues, which is where a
    report gets narrowed - rendering it unfiltered proves much less."""
    as_role("visitor")
    unfiltered = client.get(f"/data/result/{job_id_of('matches_for_sample')}")
    filtered = client.get(f"/data/result/{job_id_of('matches_for_sample')}?filter_direct_min_score=99")

    assert unfiltered.status_code == 200
    assert filtered.status_code == 200
    assert filtered.data != unfiltered.data


def test_unique_blocks_page_paginates(client, as_role):
    as_role("visitor")
    first = client.get(f"/data/result/{job_id_of('unique_blocks')}")
    second = client.get(f"/data/result/{job_id_of('unique_blocks')}?blkp=2")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.data != second.data


def test_a_job_id_nobody_knows_is_reported_not_crashed(client, as_role):
    as_role("visitor")
    response = client.get("/data/result/ffffffffffffffffffffffff")
    assert response.status_code == 200
    assert b"was not found in the system" in response.data


def test_job_page_renders_for_a_finished_job(client, as_role):
    as_role("visitor")
    response = client.get(f"/data/jobs/{job_id_of('matches_for_sample')}")
    assert response.status_code == 200


def test_unique_blocks_statistics_carries_a_sample_version(client, as_role):
    """The report names samples by id only - `statistics["by_sample_id"]` is block
    counts - so the version has to be looked up on the backend (issue #80)."""
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('unique_blocks')}")

    assert response.status_code == 200
    statistics_table = statistics_table_of(response.data.decode())
    assert ">Version<" in statistics_table
    # the versions of the three win.citadel samples the captured report covers
    for version in ("1.3.5.1", "1.3.4.0", "0.0.1.1"):
        assert version in statistics_table, f"{version} missing from the statistics table"


def test_the_yara_copy_icon_is_wired_to_the_textareas_value(client, as_role):
    """Issue #80: the copy icon used to copy `$(element).html()` out of a detached
    textarea, so it handed back the rendered markup - HTML entities for `& < >`, and
    none of the edits the reader had made to a rule that is deliberately editable.

    A lint, because it is what CI can run: `tests/testBrowser.py` clicks this icon in
    Chromium and reads the clipboard back, but playwright is not a dependency of this
    project and CI does not install it, so that module skips there. Without something
    here the old implementation can be restored verbatim and the suite stays green.
    """
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('unique_blocks')}?tab=yara")
    page = response.data.decode()

    assert response.status_code == 200
    assert 'id="yara_text"' in page, "the rule textarea the icon names is not on the page"
    assert COPY_ICON.search(page), "no copy icon calls copyTextAreaToClipboard on #yara_text"

    # base.html carries a `copy_to_clipboard` of its own, hence the camel-cased
    # needle: it matches this page's helper and the pre-#80 one, and nothing else.
    helpers = [body for body in SCRIPT_BLOCK.findall(page) if "ToClipboard" in body]
    assert len(helpers) == 1, f"expected one YARA clipboard helper on the page, found {len(helpers)}"
    code = LINE_COMMENT.sub("", helpers[0])
    assert "textarea.value" in code, "the clipboard helper never reads the textarea's value"
    for shape in COPIES_THE_MARKUP:
        assert shape not in code, f"the clipboard helper reads {shape} - that is the markup, not the value"


def test_a_long_block_stays_valid_yara_when_it_wraps(client, as_role):
    """Issue #80, "copy to clipboard break with extensively long yara strings".

    The Block column is YARA syntax and is there to be copied out. It used to be
    wrapped by breaking every 80th character, which lands mid-byte far more often
    than not: 41 of the 51 sequences in the captured report were cut inside a
    token and 23 of those left an odd-length run like "6a3", which no YARA
    compiler will take. Short sequences never wrapped, so the damage only showed
    on the long ones the issue names.

    The page's own block-length filter is what puts those on the first page: the
    default order is by score, and the hundred highest-scoring blocks of the
    captured report are all short enough that nothing wraps at all.
    """
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('unique_blocks')}?tab=blocks&min_block_length=20")

    assert response.status_code == 200
    sequences = hex_sequences_of(response.data.decode())
    assert sequences, "no blocks rendered, so nothing was checked"
    wrapped = [sequence for sequence in sequences if "\n" in sequence]
    assert len(wrapped) == len(sequences) == 18, "the filtered page is no longer the eighteen long blocks it was"
    for sequence in wrapped:
        for token in sequence.split():
            assert HEX_TOKEN.match(token), f"{token!r} is not a YARA hex byte, in: {sequence!r}"


def test_the_yara_rule_names_the_function_each_picblock_came_from(client, as_role):
    """Issue #80, "maybe include function_id ... (more robustness)".

    mcrit picks the cover blind to which function a block sits in, so a rule can
    quietly end up fingerprinting one function - and `7 of them` then dies with
    the next recompile of it. The captured report spreads its ten blocks over
    seven functions; naming them is what lets a reader see that at all.
    """
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('unique_blocks')}?tab=yara")
    page = html.unescape(response.data.decode())

    assert response.status_code == 200
    comments = RULE_PICBLOCK_COMMENT.findall(page)
    assert len(comments) == 10, f"expected the ten picblocks of the captured rule, found {len(comments)}"
    for pichash, tail in comments:
        assert tail.startswith(", function_id: "), f"{pichash} does not name the function it came from"
    # and the annotation is per block, not one id repeated over all of them
    assert len({tail for _, tail in comments}) == 7


def test_unique_blocks_statistics_table_carries_the_sorting_markup(client, as_role):
    """A markup lint, and named as one: it reads the attributes the sorting script
    reads and says nothing about what a click does. Deleting the script outright
    leaves this green, which is exactly the limit of what an HTML assertion can
    reach.

    `tests/testBrowser.py` is where the headers get clicked. That module needs
    playwright, which is not a dependency of this project and which CI does not
    install, so this is the half of the cover CI keeps.

    Worth linting even so: a formatted cell reads "2844 (66.76%)", which is not a
    number, so the raw count has to travel beside it or the column cannot be
    ordered at all.
    """
    as_role("visitor")
    response = client.get(f"/data/result/{job_id_of('unique_blocks')}")
    page = response.data.decode()

    assert response.status_code == 200
    statistics_table = statistics_table_of(page)
    assert 'class="table table-hover sortable-table"' in statistics_table, "the sorting script only touches tables marked sortable-table"
    # one text column, Version, and one per count
    assert statistics_table.count('data-sort="text"') == 1
    assert statistics_table.count('data-sort="number"') == 4
    # the raw counts of sample 0, beside the cells that render them formatted
    for count in ("4260", "2844", "611"):
        assert f'data-sort-value="{count}"' in statistics_table, f"{count} carries no sortable value"
    assert any("sortable-table" in body for body in SCRIPT_BLOCK.findall(page)), "no script on the page acts on the marked tables"


def test_unique_blocks_family_page_reads_the_versions_off_the_family(client, as_role, fake_mcrit):
    """`getFamily` answers with the family's samples, and `result_unique_blocks` is
    holding that entry before it builds the statistics table - so the Version column
    of a family job costs no request of its own.

    Asserted on the rendered page rather than on `get_sample_versions` directly,
    because the unit test below can only say the helper prefers the family; it
    cannot say the view hands it a family that has any samples in it. That is a
    property of the backend, and it is what this one pins down.
    """
    as_role("visitor")
    fake_mcrit.calls.clear()

    response = client.get(f"/data/result/{job_id_of('unique_blocks')}")

    assert response.status_code == 200
    requested = collections.Counter(name for name, _, _ in fake_mcrit.calls)
    assert requested["getFamily"] == 1
    assert requested["getSampleById"] == 0, "the family already carried the samples, so nothing had to be fetched by id"
    # and the column is populated, so "no requests" cannot mean "no versions"
    assert "1.3.5.1" in statistics_table_of(response.data.decode())


def test_the_corpus_answers_the_two_family_endpoints_differently(corpus_mcrit):
    """A guard on the fixture the test above stands on.

    `/families` and `/families/{id}` do not return the same entry: storage does not
    keep a family's sample list, so the collection cannot carry one, and only
    `FamilyResource.on_get` fills `samples` in - for one family, and only when asked.
    Serving the richer shape from both would put samples somewhere the real backend
    never does, and a view leaning on that would pass here and fail in a browser.
    """
    assert corpus_mcrit.getFamily(1).samples, "a single family must arrive with its samples"
    assert corpus_mcrit.getFamily(1, with_samples=False).samples is None
    assert all(entry.samples is None for entry in corpus_mcrit.getFamilies().values())


def test_unique_blocks_page_survives_a_backend_that_lost_a_sample(client, as_role, fake_mcrit):
    """A sample the family no longer lists falls through to a lookup by id, and a
    backend that cannot resolve it answers None. The version column has nothing to
    show for that row, which is not a reason to lose the whole report."""
    as_role("visitor")
    family = fake_mcrit.getFamily(1)
    assert family.samples, "the captured family carries no samples - see tests/fixtures/regenerate.py"
    family.samples = {key: entry for key, entry in family.samples.items() if entry.sample_id != 2}
    fake_mcrit.getSampleById = lambda sample_id, *args, **kwargs: None

    response = client.get(f"/data/result/{job_id_of('unique_blocks')}")

    assert response.status_code == 200
    statistics_table = statistics_table_of(response.data.decode())
    assert "1.3.5.1" in statistics_table, "the samples the family still lists lost their version"
    assert "0.0.1.1" not in statistics_table, "the sample nothing could resolve was given a version anyway"


class _StubSample:
    def __init__(self, sample_id, version):
        self.sample_id = sample_id
        self.version = version


class _StubFamily:
    def __init__(self, samples=None):
        self.samples = samples


class _StubClient:
    """Answers getSampleById from a dict and counts what it was asked for."""

    def __init__(self, samples):
        self.samples = samples
        self.requested = []

    def getSampleById(self, sample_id):
        self.requested.append(sample_id)
        return self.samples.get(sample_id)


def test_sample_versions_come_from_the_family_without_extra_requests():
    """getFamily already answers with the family's samples, and result_unique_blocks
    has that entry in hand before the statistics table is built."""
    from mcritweb.views.data import get_sample_versions

    client = _StubClient({})
    family = _StubFamily({"0": _StubSample(0, "1.0"), "1": _StubSample(1, "2.0")})

    assert get_sample_versions(client, family, [0, 1]) == {0: "1.0", 1: "2.0"}
    assert client.requested == []


def test_sample_versions_fall_back_to_a_lookup_per_sample():
    """The sample-job case has no family, and a backend answering a family without
    its samples lands here too."""
    from mcritweb.views.data import get_sample_versions

    client = _StubClient({7: _StubSample(7, "3.x")})

    assert get_sample_versions(client, None, [7]) == {7: "3.x"}
    assert client.requested == [7]


def test_sample_versions_omit_a_sample_the_backend_no_longer_has():
    from mcritweb.views.data import get_sample_versions

    client = _StubClient({})

    assert get_sample_versions(client, _StubFamily(None), [7]) == {}
    assert client.requested == [7]


if __name__ == "__main__":
    unittest.main()
