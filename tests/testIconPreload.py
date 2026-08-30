#!/usr/bin/python
"""The icon webfont has to start downloading with the rest of the page.

A font is not a resource the browser's preload scanner can see. It is discovered only
once the stylesheet that names it has been parsed *and* the first layout has found an
element that draws with it, which puts it a full render-blocking round behind everything
else in <head>. Measured on this app with headless Chromium against a local server: the
landing page fires all seven stylesheets, all eight scripts and both logos in one burst,
and `fa-solid-900.woff2` only follows a clear gap after the last of them - 145 ms at a
390x844 viewport, 152 ms at 1280x800, and that against a server one hop away. all.css
declares `font-display: block`, so until it lands every `<i class="fa-...">` is a blank
box - the navbar's Explore entries among them, which is what issue #62 asks about.

The one attribute that is easy to get wrong is `crossorigin`. Fonts are fetched in CORS
mode even same-origin, so a preload without it does not match the fetch the CSS later
makes and the file is downloaded twice: dropping the attribute and re-measuring gave two
requests for the same 150 KB, one at +221 ms and one at +400 ms. Hence a test of its own.
"""

import logging
import re
import unittest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

PRELOAD_LINK = re.compile(rb"<link\s[^>]*rel=\"preload\"[^>]*>")
SOLID_FONT = b"webfonts/fa-solid-900.woff2"


def preload_links(html):
    return PRELOAD_LINK.findall(html)


def test_the_icon_font_is_preloaded(client):
    """Unauthenticated - the preload lives in base.html, so it is on every page."""
    response = client.get("/login")
    assert response.status_code == 200
    links = [link for link in preload_links(response.data) if SOLID_FONT in link]
    assert links, f"no preload for the icon font in:\n{preload_links(response.data)}"
    link = links[0]
    assert b'as="font"' in link, link
    assert b'type="font/woff2"' in link, link


def test_the_preload_is_crossorigin(client):
    """Without it the font is fetched twice - once for the preload in no-cors mode and
    once for the CSS in cors mode - which costs more than the preload saves."""
    response = client.get("/login")
    link = next(link for link in preload_links(response.data) if SOLID_FONT in link)
    assert b"crossorigin" in link, link


def test_the_preloaded_font_is_actually_served(client):
    """A FontAwesome upgrade that renames the file would otherwise leave a preload
    pointing at a 404 that nothing else in the app notices."""
    response = client.get("/login")
    link = next(link for link in preload_links(response.data) if SOLID_FONT in link)
    href = re.search(rb'href="([^"]+)"', link).group(1).decode()

    font = client.get(href)
    assert font.status_code == 200, f"{href} -> {font.status_code}"
    assert len(font.get_data()) > 0


def test_the_navbar_draws_with_the_face_that_is_preloaded(client, as_role):
    """The preload is unconditional, so it is only justified while every page really
    needs the solid face. base.html's help icon is what guarantees that today - if it
    goes, the preload becomes dead weight on pages that never draw an icon."""
    anonymous = client.get("/login")
    assert re.search(rb'class="(fas|fa-solid)[ "]', anonymous.data), \
        "no solid icon on an unauthenticated page - reconsider preloading unconditionally"

    as_role("visitor")
    logged_in = client.get("/")
    assert logged_in.status_code == 200
    assert re.search(rb'class="(fas|fa-solid)[ "]', logged_in.data)


def test_only_the_face_every_page_draws_with_is_preloaded(client):
    """Preloading the regular, brands or v4-compatibility faces would warn in the console
    and waste the transfer on every page that never uses them."""
    response = client.get("/login")
    fonts = [link for link in preload_links(response.data) if b'as="font"' in link]
    assert len(fonts) == 1, fonts
    for unused in (b"fa-regular-400", b"fa-brands-400", b"fa-v4compatibility"):
        assert unused not in fonts[0], fonts[0]


if __name__ == "__main__":
    unittest.main()
