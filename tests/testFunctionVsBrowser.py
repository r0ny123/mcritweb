#!/usr/bin/python
"""The loop visualisation on the function comparison page, driven in a browser.

Issue #69 asks for the loop visualisation to be fixed. All of it is script: the two
CFGs are fetched, laid out by dagre and annotated by `static/trace_CFG/main_duo.js`
after the page has loaded, so nothing about it is visible to a test that renders the
template and reads the HTML back. The markup assertions in testResultPages.py are
what CI keeps; these are the tests that watch the boundaries actually get drawn.

The harness is the offline one the rest of the suite uses - `CorpusMcritClient`
behind MCRIT_CLIENT_FACTORY, no backend and no network - served on a loopback port
so Chromium can load it. Loop detection is `mcritweb.views.cfg_explorer_detector`,
which is ours and needs no backend either, so what the page draws is driven by real
loops in real captured control flow graphs.

`playwright` is not a dependency of this project and CI does not install it, so this
module skips there rather than failing.
"""

import json
import logging
import threading

import pytest
from werkzeug.serving import make_server

sync_api = pytest.importorskip("playwright.sync_api", reason="playwright is not installed")

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

#: The page's own timeout, for a load and for anything a script does after it.
#: Generous, because it is only ever paid in full when a test is about to fail.
SCRIPT_TIMEOUT_MS = 20000

#: Two functions from the captured corpus, one per reference sample, both of which
#: the loop detector finds several loops in - including nested ones in B, so the
#: depth shading has something to distinguish. Only the reference pool keeps its
#: control flow graph, so the panels cannot be built from any other function.
FUNCTION_A = 84
FUNCTION_B = 943


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


@pytest.fixture
def live_server(app):
    """The app under test on a loopback port, for the seconds a test needs it.

    `client` is a WSGI stub with no socket behind it, so a browser cannot reach it.
    Port 0 lets the OS pick, so concurrent runs do not collide.
    """
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)
        server.server_close()


@pytest.fixture
def browser_page(app, live_server, make_user):
    """A Chromium page already logged in as a visitor, on `live_server`.

    The session cookie is signed with the app's own session interface rather than
    driven through the login form: this module is about what the comparison page's
    scripts do, and going through the form would make every test here fail for a
    change to the login markup instead.
    """
    user_id = make_user(role="visitor")
    cookie = app.session_interface.get_signing_serializer(app).dumps({"user_id": user_id})

    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except sync_api.Error as error:
            pytest.skip(f"no Chromium for playwright to drive: {error}")
        try:
            context = browser.new_context()
            context.add_cookies([{
                "name": app.config["SESSION_COOKIE_NAME"],
                "value": cookie,
                "domain": "127.0.0.1",
                "path": "/",
            }])
            page = context.new_page()
            page.set_default_timeout(SCRIPT_TIMEOUT_MS)
            yield page
        finally:
            browser.close()


@pytest.fixture
def comparison_page(browser_page, live_server):
    """The function-vs page with both CFGs laid out and annotated.

    Each panel is two requests deep - the dot graph, then loop detection - and only
    draws once both have answered, so waiting for blocks in *both* containers is
    what says the page is finished.
    """
    browser_page.goto(f"{live_server}/data/matches/function/{FUNCTION_A}/{FUNCTION_B}")
    for panel in ("a", "b"):
        browser_page.wait_for_selector(f"#graphContainer_{panel} g.node", state="attached")
    return browser_page


def detected_loops(page, function_id):
    """The loops the server reports for one function, asked for as the page asks.

    Same two endpoints in the same order, including the `\\l` substitution made
    before posting - so this is what the panel was handed, not a re-derivation of
    it. Issued from inside the page because both routes need the session, and
    playwright's request context does not carry the context's cookies.
    """
    return json.loads(page.evaluate(
        """async function(functionId) {
            const dot = await (await fetch('/explore/fetchDotGraph/' + functionId)).text();
            const response = await fetch('/explore/findLoops/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'text/plain',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content,
                },
                body: dot.replace(/\\\\l/g, "\\n"),
            });
            return await response.text();
        }""",
        function_id,
    ))


def boundary_geometry(page, panel):
    """Where each of a panel's loop boundaries is, in screen coordinates."""
    return page.evaluate(
        """panel => {
            const group = document.getElementById('bgFill_' + panel);
            if (!group) { return null; }
            const inner = document.querySelector('#graphContainer_' + panel + ' g');
            return {
                behind_the_graph: inner.firstElementChild === group,
                paths: Array.from(group.querySelectorAll('path')).map(path => {
                    const box = path.getBoundingClientRect();
                    return {left: box.left, top: box.top, right: box.right, bottom: box.bottom,
                            fill: path.getAttribute('fill')};
                }),
            };
        }""",
        panel,
    )


def block_geometry(page, panel, block_names):
    """Where each named block of a panel was rendered, in screen coordinates.

    The rendered blocks are looked up through the page's own per-panel registry,
    which is how every other consumer on the page finds them; a block the renderer
    never produced comes back as null rather than throwing.
    """
    return page.evaluate(
        """([panel, names]) => names.map(name => {
            const nodes = window.cfgPanels[panel].nodes;
            if (!Object.prototype.hasOwnProperty.call(nodes, name)) { return null; }
            const box = nodes[name].node().getBoundingClientRect();
            return {left: box.left, top: box.top, right: box.right, bottom: box.bottom};
        })""",
        [panel, block_names],
    )


def encloses(outer, inner):
    return (outer["left"] <= inner["left"] and outer["top"] <= inner["top"]
            and outer["right"] >= inner["right"] and outer["bottom"] >= inner["bottom"])


@pytest.mark.parametrize("panel,function_id", [("a", FUNCTION_A), ("b", FUNCTION_B)])
def test_every_detected_loop_gets_a_boundary_behind_its_panel(comparison_page, panel, function_id):
    """Issue #69's "fix loop visualization". `Show Loop Boundaries` used to toggle a
    `#bgFill` that nothing on this page ever created, because loopify_dagre draws it
    against a rewritten layout this page does not render. Both panels now draw their
    own, one per loop, underneath the blocks rather than over them."""
    loops = detected_loops(comparison_page, function_id)
    assert loops, f"function {function_id} has no loops to draw"

    geometry = boundary_geometry(comparison_page, panel)
    assert geometry is not None, f"panel {panel} drew no loop boundaries at all"
    assert geometry["behind_the_graph"], "the boundaries are painted over the blocks, not behind them"
    assert len(geometry["paths"]) == len(loops)
    for path in geometry["paths"]:
        assert path["right"] > path["left"] and path["bottom"] > path["top"], "a boundary has no area"


@pytest.mark.parametrize("panel,function_id", [("a", FUNCTION_A), ("b", FUNCTION_B)])
def test_each_boundary_encloses_the_blocks_of_one_loop(comparison_page, panel, function_id):
    """Drawing the right number of shapes says nothing about where they are. Every
    loop has to have a boundary that covers all of its blocks - a hull built from
    the wrong panel's layout, or from the blocks of some other loop, would still
    count correctly here and cover nothing."""
    loops = detected_loops(comparison_page, function_id)
    paths = boundary_geometry(comparison_page, panel)["paths"]

    for loop in loops:
        blocks = [block for block in block_geometry(comparison_page, panel, loop["nodes"]) if block]
        assert blocks, f"none of loop {loop['backedge']}'s blocks were rendered"
        assert any(all(encloses(path, block) for block in blocks) for path in paths), (
            f"no boundary in panel {panel} covers loop {loop['backedge']}"
        )


def test_the_checkbox_takes_the_boundaries_off_and_puts_them_back(comparison_page):
    """The control shipped disabled, with a title saying it had nothing to toggle.
    It is a live checkbox again, and it has to reach both panels - the one-graph
    page toggles a single `#bgFill` by id, which would leave a panel behind here."""
    checkbox = comparison_page.locator("#loopBgFill")
    assert checkbox.is_enabled(), "the loop boundary control is still disabled"
    assert checkbox.is_checked(), "boundaries are meant to start visible"

    def displays():
        return comparison_page.eval_on_selector_all(
            "g.bgFill", "groups => groups.map(group => getComputedStyle(group).display)"
        )

    assert len(displays()) == 2, "both panels should have a boundary group"
    assert "none" not in displays()

    checkbox.uncheck()
    assert displays() == ["none", "none"]

    # a panel draws its boundaries only once its own two requests have answered,
    # which can be well after the reader touched the control - so a panel finishing
    # late must not put back what was just taken off
    comparison_page.evaluate("() => renderLoopBoundaries('b')")
    assert displays() == ["none", "none"]

    checkbox.check()
    assert "none" not in displays()
    assert len(displays()) == 2, "re-drawing a panel left it with two boundary groups"
