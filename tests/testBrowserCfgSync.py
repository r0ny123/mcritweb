#!/usr/bin/python
"""The CFG pane synchronisation of issue #74, which only a browser can answer.

What #74 added is a zoom handler in `static/trace_CFG/main_duo.js` that mirrors one
pane's view onto the other, and a checkbox to turn it off. Reading the rendered HTML
back would settle that the checkbox is *present* and nothing else - a page can carry
it and mirror nothing - and the graphs are not in the HTML at all: the page builds
both from same-origin XHRs (`/explore/fetchDotGraph/<id>` and `/explore/findLoops/`)
after load.

The harness is the offline one the rest of the suite uses - `CorpusMcritClient`
behind MCRIT_CLIENT_FACTORY, no backend and no network - served on a loopback port so
Chromium can reach it. Rendering the comparison page offline is new here, and needed
`getMatchFunctionVs` and `getMatchesForPicHash` on that fake.

`playwright` is not a dependency of this project and CI does not install it, so this
module skips there rather than failing. Nothing CI runs covers this behaviour.
"""

import json

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="playwright is not installed")

#: Two Functions from different reference Samples, both with an xcfg the CFG route can
#: render. Deliberately *not* the same size - 42 blocks against 47 - so the two panes
#: get different fit-to-view scales and a pane that merely fitted itself cannot pass
#: for one that mirrored the other.
FUNCTION_ID_A = 9
FUNCTION_ID_B = 962

#: Both graphs arrive over two chained XHRs each, then dagre lays them out.
RENDER_TIMEOUT_MS = 30000


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


@pytest.fixture
def comparison_page(app, live_server, make_user):
    """Chromium on the function comparison page, both CFGs rendered, logged in.

    The session cookie is signed with the app's own session interface rather than
    driven through the login form, so a change to the login markup fails the tests
    that are about login instead of these.
    """
    from flask.sessions import SecureCookieSessionInterface

    user_id = make_user(role="visitor")
    serializer = SecureCookieSessionInterface().get_signing_serializer(app)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1600, "height": 1000})
        context.add_cookies([{
            "name": app.config.get("SESSION_COOKIE_NAME") or "session",
            "value": serializer.dumps({"user_id": user_id}),
            "url": live_server,
        }])
        page = context.new_page()
        page.goto(f"{live_server}/data/matches/function/{FUNCTION_ID_A}/{FUNCTION_ID_B}")
        # both panes are fetched independently; wait until each has been laid out and
        # fitted, which is the first thing to write a transform onto its inner <g>
        page.wait_for_function(
            r"['a', 'b'].every(function(id){"
            r"  var g = document.querySelector('#graphContainer_' + id + ' > g');"
            r"  return g && /scale\(/.test(g.getAttribute('transform') || '');"
            r"})",
            timeout=RENDER_TIMEOUT_MS,
        )
        try:
            yield page
        finally:
            context.close()
            browser.close()


def _views(page):
    """The scale each pane's inner <g> is currently drawn at, as {"a": s, "b": s}."""
    return json.loads(page.evaluate(
        r"JSON.stringify(['a', 'b'].reduce(function(acc, id){"
        r"  var transform = document.querySelector('#graphContainer_' + id + ' > g')"
        r"    .getAttribute('transform');"
        r"  acc[id] = parseFloat(/scale\(([-0-9.e]+)\)/.exec(transform)[1]);"
        r"  return acc;"
        r"}, {}))"
    ))


def _zoom_pane_a(page):
    """Wheel over the left pane, the way a reader zooms it.

    The CFGs sit below the comparison table, so the pane has to be brought into the
    viewport first - `bounding_box` is viewport-relative and the mouse cannot be put
    outside it.
    """
    pane = page.locator("#graphContainer_a")
    pane.scroll_into_view_if_needed()
    box = pane.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -240)
    page.wait_for_timeout(250)


def test_zooming_one_pane_zooms_the_other(comparison_page):
    """The point of issue #74: the passive pane follows the one being driven."""
    before = _views(comparison_page)
    _zoom_pane_a(comparison_page)
    after = _views(comparison_page)

    assert after["a"] != before["a"], "the wheel did not reach the left pane at all"
    assert after["b"] != before["b"], "the right pane did not follow the left one"
    # what is mirrored is the view *relative* to each pane's own fit, so the two panes
    # keep the same zoom factor away from fitted rather than the same absolute scale
    assert after["a"] / before["a"] == pytest.approx(after["b"] / before["b"], rel=1e-6)


def test_unchecking_the_box_stops_the_mirroring(comparison_page):
    """The checkbox has to be a control, not decoration - it is checked by default."""
    comparison_page.uncheck("#enableGraphSync")
    before = _views(comparison_page)
    _zoom_pane_a(comparison_page)
    after = _views(comparison_page)

    assert after["a"] != before["a"], "the wheel did not reach the left pane at all"
    assert after["b"] == before["b"], "the right pane moved with synchronisation off"
