#!/usr/bin/python
"""What the dark theme looks like, which only a browser can answer.

Reading the HTML back settles that `data-theme="dark"` reached the page and that no
template spells a colour out - testTheme.py does both. Neither says what the page
actually paints: the palette lives in `style.css`, the widgets that ignore it live
in vendored Bootstrap, and whether the second file catches the first is a question
about the cascade, so it is asked here with `getComputedStyle`.

The check is deliberately blunt: on a dark page, nothing may paint an opaque light
background. That is the failure mode of a half-themed application - one white table
or one white modal in the middle of a dark page - and it is what the vendored
stylesheets do if nothing overrides them.

The harness is the offline one the rest of the suite uses - `CorpusMcritClient`
behind MCRIT_CLIENT_FACTORY, no backend and no network - served on a loopback port
so Chromium can load it, exactly as in testBrowser.py.

`playwright` is not a dependency of this project and CI does not install it, so this
module skips there rather than failing.
"""

import logging

import pytest
from fixtureData import job_id_of

sync_api = pytest.importorskip("playwright.sync_api", reason="playwright is not installed")

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

PAGE_TIMEOUT_MS = 10000

#: Relative luminance above which a background is "a light surface". 0.5 is well
#: clear of both palettes - the dark ground is 0.012 and Bootstrap's white is 1.0 -
#: so this fails on a surface that was missed, not on a shade that was debated.
LIGHT_SURFACE = 0.5

#: Enough of the application to cover the widgets the vendored stylesheets own:
#: navbar and dropdowns everywhere, tables and pagination on the listings, the
#: nav-pills, drag panels and form controls on settings, DataTables on jobs, the
#: rendered markdown on help, and the score-tinted result tables last - those are
#: painted by ScoreColorProvider rather than by CSS.
PAGES = [
    "/",
    "/settings",
    "/explore/families",
    "/explore/samples",
    "/explore/search?query=test",
    "/data/jobs",
    "/help",
    f"/data/result/{job_id_of('matches_for_sample')}",
    f"/data/result/{job_id_of('cross_compare')}",
    f"/data/linkhunt/{job_id_of('matches_for_sample')}",
]

#: Walks the rendered page and reports every opaque background lighter than the
#: threshold, with enough of a description to find it again. Elements too small to
#: see, and the ones a closed modal or dropdown leaves collapsed, are skipped - and
#: so is any element whose background the *view* wrote into its style attribute.
#: Those are the score palettes, which are deliberately saturated in the cross
#: compare matrix and are covered by ScoreColorProvider's own tests and by the
#: contrast test below; everything else here comes from a stylesheet, which is what
#: the theme is responsible for.
FIND_LIGHT_SURFACES = """
(threshold) => {
  const channel = (value) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const luminance = (r, g, b) =>
    0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
  const parse = (value) => {
    const m = value.match(/rgba?\\(([\\d.]+),\\s*([\\d.]+),\\s*([\\d.]+)(?:,\\s*([\\d.]+))?\\)/);
    if (!m) return null;
    return {r: +m[1], g: +m[2], b: +m[3], a: m[4] === undefined ? 1 : +m[4]};
  };
  const describe = (el) => {
    const id = el.id ? '#' + el.id : '';
    const cls = typeof el.className === 'string' && el.className
      ? '.' + el.className.trim().split(/\\s+/).join('.') : '';
    return el.tagName.toLowerCase() + id + cls;
  };
  const findings = [];
  for (const el of document.querySelectorAll('*')) {
    const rect = el.getBoundingClientRect();
    if (rect.width < 6 || rect.height < 6) continue;
    const style = getComputedStyle(el);
    if (style.visibility === 'hidden' || style.opacity === '0') continue;
    if (el.style && el.style.backgroundColor) continue;
    // a plate behind a logo: the Fraunhofer mark is a third party's and keeps the
    // light ground it was drawn for rather than being recoloured
    if (!el.textContent.trim() && el.querySelector('img')) continue;
    const bg = parse(style.backgroundColor);
    if (!bg || bg.a < 0.5) continue;
    if (luminance(bg.r, bg.g, bg.b) > threshold) {
      findings.push(describe(el) + ' -> ' + style.backgroundColor);
    }
  }
  return findings;
}
"""


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """Wire the app in this module to the captured corpus (see conftest)."""
    return corpus_mcrit


@pytest.fixture
def dark_page(app, live_server, make_user):
    """A Chromium page logged in as a visitor whose stored theme is dark.

    The cookie is signed with the app's own session interface rather than driven
    through the login form, so a change to that form cannot fail these.
    """
    from mcritweb.db import UserInfo

    user_id = make_user(role="visitor")
    with app.app_context():
        user_info = UserInfo.fromDb(user_id=user_id)
        user_info.theme = "dark"
        user_info.saveToDb()
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
            page.set_default_timeout(PAGE_TIMEOUT_MS)
            yield page
        finally:
            browser.close()


@pytest.mark.parametrize("path", PAGES)
def test_no_page_paints_a_light_surface_under_the_dark_theme(dark_page, live_server, path):
    response = dark_page.goto(live_server + path)

    assert response.status == 200, f"{path} did not render"
    assert dark_page.get_attribute("html", "data-theme") == "dark"
    findings = dark_page.evaluate(FIND_LIGHT_SURFACES, LIGHT_SURFACE)
    assert not findings, f"{path} still paints a light surface: {findings}"


def test_the_navigation_menus_are_themed_when_they_open(dark_page, live_server):
    """A dropdown is display:none until it is opened, so the sweep above never sees
    one - and `.dropdown-menu` is painted white by Bootstrap, not by us."""
    dark_page.goto(live_server + "/")
    dark_page.click("#navbarDropdownExplore")
    dark_page.wait_for_selector(".dropdown-menu.show")

    findings = dark_page.evaluate(FIND_LIGHT_SURFACES, LIGHT_SURFACE)

    assert not findings, f"the open menu paints a light surface: {findings}"


def test_the_submit_modal_is_themed_when_it_opens(dark_page, live_server):
    """Same for the drop-a-file modal base.html carries on every page."""
    dark_page.goto(live_server + "/")
    dark_page.evaluate("new bootstrap.Modal(document.getElementById('submitFileModal')).show()")
    dark_page.wait_for_selector("#submitFileModal.show")

    findings = dark_page.evaluate(FIND_LIGHT_SURFACES, LIGHT_SURFACE)

    assert not findings, f"the open modal paints a light surface: {findings}"


def test_result_text_stays_readable_on_a_score_tinted_cell(dark_page, live_server):
    """ScoreColorProvider mixes its hues into the page rather than into white, so on
    a dark page the tints come out dark - and the text on them, which the templates
    used to pin to `black`, has to come out light."""
    dark_page.goto(live_server + f"/data/result/{job_id_of('matches_for_sample')}")

    contrasts = dark_page.evaluate("""
    () => {
      const channel = (v) => { const c = v / 255;
        return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
      const luminance = (r, g, b) =>
        0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
      const parse = (value) => {
        const m = value.match(/rgba?\\(([\\d.]+),\\s*([\\d.]+),\\s*([\\d.]+)/);
        return m ? [+m[1], +m[2], +m[3]] : null;
      };
      const out = [];
      for (const row of document.querySelectorAll('tr[style*="background-color"]')) {
        const bg = parse(getComputedStyle(row).backgroundColor);
        if (!bg) continue;
        for (const cell of row.querySelectorAll('td')) {
          if (!cell.textContent.trim()) continue;
          const fg = parse(getComputedStyle(cell).color);
          const a = luminance(...fg), b = luminance(...bg);
          out.push([(Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05),
                    getComputedStyle(row).backgroundColor]);
        }
      }
      return out;
    }
    """)

    assert contrasts, "no score-tinted row was rendered, so nothing was measured"
    worst = min(contrasts, key=lambda pair: pair[0])
    assert worst[0] >= 4.5, f"text on a score-tinted row is unreadable: {worst}"
