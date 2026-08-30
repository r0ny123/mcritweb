#!/usr/bin/python
"""What base.html makes every page download, and why.

Issue #63: "even if js is cached, it is still always renderblocking", and its first
bullet, "remove data-tables js/css once it is not needed anymore".

Two libraries in base.html were paid for by every page in the app:

  jquery-ui.js                529 KB  }  623 KB of render-blocking JavaScript
  jquery.dataTables.min.js     90 KB  }  and 41 KB of CSS, everywhere
  dataTables.bootstrap5.min.js  4 KB  }
  jquery-ui.css                37 KB
  dataTables.bootstrap5.min.css 4 KB

jQuery UI served exactly one `.sortable()` call, on the cross compare result page.
DataTables served exactly one `.DataTable()` call, on the jobs page - against the
selector `#job-table`, which that page never renders: it builds its table with
`table_id=active`, the job method. So DataTables did nothing at all, anywhere.

Measured with Chromium, total decoded bytes per page:

    page                    master    after
    /                        1667 KB   1017 KB
    /explore/samples         1667 KB   1017 KB
    /data/jobs               1667 KB   1017 KB
    /data/result/<cross>     1691 KB   1595 KB   (keeps jQuery UI, loses DataTables)

and behaviour identical on both: `.sortable()` still applied on the cross compare,
the clipboard tooltips still get Bootstrap instances rather than jQuery UI's, no
console errors anywhere.
"""

import logging
import pathlib
import re
import unittest

import pytest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

TEMPLATE_ROOT = pathlib.Path(__file__).resolve().parents[1] / "mcritweb" / "templates"
BASE = TEMPLATE_ROOT / "base.html"

#: assets base.html must not load, and where they belong instead
PAGE_SPECIFIC = {
    "jquery-ui.js": "result_cross.html",
    "jquery-ui.css": "result_cross.html",
}

#: assets no template should load at all any more
RETIRED = ["jquery.dataTables.min.js", "dataTables.bootstrap5.min.js", "dataTables.bootstrap5.min.css"]


@pytest.mark.parametrize("asset", sorted(PAGE_SPECIFIC))
def test_a_page_specific_library_is_not_loaded_by_every_page(asset):
    assert asset not in code_of(BASE), f"base.html makes every page download {asset}"


@pytest.mark.parametrize("asset", sorted(PAGE_SPECIFIC))
def test_it_is_loaded_by_the_page_that_needs_it(asset):
    owner = TEMPLATE_ROOT / PAGE_SPECIFIC[asset]
    assert asset in code_of(owner), f"{owner.name} calls into {asset} but does not load it"


JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.S)


def code_of(path):
    """The template with its Jinja comments stripped.

    These tests look for *calls*, and the comments explaining why a library was moved
    naturally name the call they are about - so scanning the raw text would find the
    prose and report the library as still in use.
    """
    return JINJA_COMMENT.sub("", path.read_text())


def templates_containing(needle):
    return {path.name for path in TEMPLATE_ROOT.rglob("*.html") if needle in code_of(path)}


@pytest.mark.parametrize("asset", RETIRED)
def test_a_retired_library_is_not_loaded_anywhere(asset):
    """DataTables' one initialiser selected an element the app never renders."""
    loaded_by = templates_containing(asset)
    assert loaded_by == set(), f"{asset} is back, in {sorted(loaded_by)}"


def test_nothing_calls_datatables_any_more():
    callers = templates_containing(".DataTable(")
    assert callers == set(), f"{sorted(callers)} calls .DataTable() but the library is no longer loaded"


def test_the_sortable_call_and_its_library_are_on_the_same_page():
    """The one thing jQuery UI is still here for. If this call moves, the library has
    to move with it - or come out."""
    callers = templates_containing(".sortable(")
    assert callers == {"result_cross.html"}, f"jQuery UI is loaded by result_cross.html but called from {sorted(callers)}"


def test_jquery_itself_stays_in_base(): 
    """It is not page-specific: 23 inline blocks across the tree open with `$(...)`,
    including two in base.html itself. Moving it is issue #63's "consider removing
    jquery", which is a different and much larger change."""
    assert "jquery.js" in code_of(BASE)


def test_the_pages_that_lost_a_library_still_render(client, as_role):
    as_role("visitor")
    for path in ("/", "/explore/samples", "/explore/families", "/data/jobs", "/settings"):
        assert client.get(path).status_code == 200, path


def test_no_page_references_an_asset_that_is_not_shipped():
    """A ratchet with a wider reach than this change: a moved or renamed asset leaves a
    404 that nothing else in the suite notices, because a missing script does not stop a
    page returning 200."""
    static_root = TEMPLATE_ROOT.parent / "static"
    referenced = set()
    for path in TEMPLATE_ROOT.rglob("*.html"):
        referenced |= set(re.findall(r"filename='([^']+)'", path.read_text()))
        referenced |= set(re.findall(r'filename="([^"]+)"', path.read_text()))

    missing = sorted(name for name in referenced if not (static_root / name).exists())
    assert missing == [], f"templates reference static files that do not exist: {missing}"


if __name__ == "__main__":
    unittest.main()
