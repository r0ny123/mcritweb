#!/usr/bin/python
"""The family-name type-ahead renders suggestions as HTML, so its data must be escaped.

`static/autocomplete.js` is vendored third-party code - byte-for-byte upstream
`gch1p/bootstrap-5-autocomplete` at 5ce977959b12, see AGENTS.md. Its `createItem`
builds each suggestion by interpolating the label and the value into an HTML string,
and `ce()` assigns that string to `innerHTML`. A family name is chosen by whoever
submits or renames a family, so a name that *is* markup becomes script the moment
someone opens the edit-family/edit-sample modal and types a matching character. Two
sinks, not one: the button's text content, and the `data-label`/`data-value`
attributes the same value is interpolated into unescaped.

`|tojson` at the two call sites protects the transport - the name reaches the browser
as a correct JS string - and that is all it protects. The sink is in JavaScript, one
`innerHTML` further on, and issue #85's ratchet in `testScriptEscaping.py` does not
reach it. AGENTS.md forbids patching a vendored asset, so the escaping is done where
the data is built: the templates hand the widget names that are already HTML-escaped.

That fix has a known, bounded cost, pinned below by
`test_the_highlighter_severs_an_entity` rather than left to a comment nobody rereads:
the widget slices the *escaped* label at offsets it measured in that same escaped
string, so a lookup straddling an entity splits it and the suggestion renders as
`R&amp;D` instead of `R&D`. Display only - the label is escaped either way, and
`data-label` still round-trips to the original - and it cannot be fixed from the call
site, because `item.label` (`autocomplete.js:110`) is the single value the matcher
(`:114`), the highlight index (`:70-72`), the rendered slices (`:75-77`) and the
attribute (`:90`) all read. See AGENTS.md for the full argument.

Four tests, deliberately not redundant:

`test_the_type_ahead_data_is_html_escaped` is offline and runs everywhere. It decodes
the JS string literals the page actually emits and asserts none of them still carries
raw markup - not just `<`, but `"` and `'` too, since `data-label="..."` is an
attribute and a bare quote there is an event handler.

`test_every_type_ahead_builds_its_data_through_the_escaping_filter` is the ratchet.
Escaping at the call site is only as good as the next call site, and it checks the
data *expression* rather than looking for the filter's name somewhere in the block -
a comment mentioning the filter used to be enough to satisfy it.

`test_a_family_name_cannot_execute_in_the_type_ahead` drives a real browser, because
the sink is a browser behaviour and no amount of reading the response proves it is
shut. Two payloads at once - one that opens a tag, one that breaks out of the
`data-label` attribute - and it asserts neither ran, both still read as text, the
prefix is still highlighted, and selecting one puts the *unescaped* name in the field.

`test_the_highlighter_severs_an_entity` is the honest record of the cost above.

The browser tests need playwright with a chromium build; without either they skip
rather than fail, so the offline pair is what CI is guaranteed to run.
"""

import json
import os
import re
import threading

import pytest
from markupsafe import escape
from mcrit.storage.FamilyEntry import FamilyEntry

#: Opens a tag from the button's text content. `<img src=q onerror=...>` needs no
#: `<script>` element, so it fires from an `innerHTML` assignment where a script tag
#: would not.
TAG_PAYLOAD = 'zz<img src=q onerror="window.__pwned=1">'

#: Breaks out of `data-label="..."` at `autocomplete.js:90` without ever using `<`.
#: A fix that escaped only the angle brackets would shut the first payload and leave
#: this one wide open, which is why both are typed in the same pass.
ATTRIBUTE_PAYLOAD = 'zz" onmouseover="window.__pwned=2'

#: Both payloads share a prefix so one lookup renders both suggestions.
PAYLOADS = (TAG_PAYLOAD, ATTRIBUTE_PAYLOAD)
LOOKUP = "zz"

#: A name that is not an attack at all - it just contains a character the escaping has
#: to encode - and a lookup that ends in the middle of the resulting entity.
ENTITY_NAME = "R&D"
ENTITY_LOOKUP = "R&"

#: The families the names are written onto. Not family 0 - that one has an empty name
#: in the corpus, and an empty name is a different edge case.
POISONED_FAMILY_IDS = (1, 2)
ENTITY_FAMILY_ID = 3

#: Pages carrying the family type-ahead: the four explore pages reach it through
#: `js/ac_family_names.html`, `/data/submit` through the `submit_or_query_dropzone`
#: macro. Both call sites, because each builds the widget's data for itself.
TYPE_AHEAD_PAGES = (
    "/explore/families",
    "/explore/samples",
    "/explore/families/1",
    "/explore/samples/0",
    "/data/submit",
)

#: The call site that still ships its list in the page, so the names are in the markup
#: and can be read back out of it. The four explore pages fetch theirs from
#: `/explore/family_names` as the user types (issue #77), so there is nothing in their
#: source to inspect - `test_the_endpoint_escapes_what_it_hands_the_type_ahead` is
#: their half of this, and the browser tests below drive both kinds end to end.
SHIPPED_TYPE_AHEAD_PAGES = ("/data/submit",)

#: Where the fetched half gets its suggestions - `explore.family_names`, spelled the
#: way the route is (the endpoint name and the URL differ).
FAMILY_NAMES_URL = "/explore/familyNames"

#: The pages the browser test can drive. `/explore/families/<id>` is missing on
#: purpose: it includes the same `js/ac_family_names.html` partial, but its sample
#: table comes back empty under the offline corpus - `fixtureData._page` does not
#: model mcrit's `field:value` query parser - so the edit modal, and with it the
#: field to type into, is never rendered. The markup test above still covers it.
BROWSER_PAGES = tuple(page for page in TYPE_AHEAD_PAGES if page != "/explore/families/1")

#: The field the widget is attached to, per call site. `#family` is the dropzone's.
FIELD_SELECTOR = "#family_new_name, #sample_family_name, #family"

#: Characters that must not survive into a value the widget renders. `<` and `>` open
#: a tag in the button's text; `"` and `'` end the attribute at `autocomplete.js:90`,
#: and an attribute break needs no angle bracket at all. `&` is deliberately absent -
#: escaping *produces* `&`, so forbidding it would fail on correct output.
MARKUP_CHARACTERS = ('<', '>', '"', "'")

SCRIPT_BLOCK = re.compile(r"<script\b.*?</script\s*>", re.IGNORECASE | re.DOTALL)
JS_STRING = re.compile(r'"(?:[^"\\\n]|\\.)*"')

PACKAGE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcritweb")
TEMPLATE_ROOT = os.path.join(PACKAGE_ROOT, "templates")
STATIC_ROOT = os.path.join(PACKAGE_ROOT, "static")


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    """The type-ahead is built from the backend's family list, so serve real rows."""
    return corpus_mcrit


def rename_family(backend, family_id, name):
    entry = backend._families[family_id]
    backend._families[family_id] = FamilyEntry.fromDict(dict(entry.toDict(), family_name=name))


@pytest.fixture
def poisoned_backend(fake_mcrit):
    """Rename corpus families to the payloads, the way `explore.modifyFamily` would."""
    for family_id, payload in zip(POISONED_FAMILY_IDS, PAYLOADS):
        rename_family(fake_mcrit, family_id, payload)
    rename_family(fake_mcrit, ENTITY_FAMILY_ID, ENTITY_NAME)
    return fake_mcrit


def autocomplete_scripts(markup):
    """Every `<script>` block on the page that constructs the type-ahead."""
    return [block for block in SCRIPT_BLOCK.findall(markup) if "new Autocomplete(" in block]


@pytest.mark.parametrize("path", SHIPPED_TYPE_AHEAD_PAGES)
def test_the_type_ahead_data_is_html_escaped(client, as_role, poisoned_backend, path):
    """No string handed to the widget may still contain raw markup.

    Asserted on the decoded values rather than on the response bytes: `|tojson` writes
    `<` as `\\u003c` and `&` as `\\u0026`, so a substring search over the raw response
    cannot tell an escaped name from an unescaped one.
    """
    as_role("admin")

    response = client.get(path)
    assert response.status_code == 200
    markup = response.data.decode()

    scripts = autocomplete_scripts(markup)
    assert scripts, f"no autocomplete script block found on {path} - the scan missed it"

    seen = set()
    for script in scripts:
        for literal in JS_STRING.findall(script):
            value = json.loads(literal)
            for character in MARKUP_CHARACTERS:
                assert character not in value, (
                    f"{path} hands the type-ahead {value!r}, which still carries "
                    f"{character!r} - the widget writes it into innerHTML and into a "
                    f"data-label attribute, and both read it as markup"
                )
            seen.add(value)

    for payload in PAYLOADS:
        assert str(escape(payload)) in seen, (
            f"the poisoned family name {payload!r} never reached the type-ahead on "
            f"{path} - the test is not exercising what it claims to"
        )


def test_the_endpoint_escapes_what_it_hands_the_type_ahead(client, as_role, poisoned_backend):
    """The other producer. Since issue #77 the family type-ahead on the explore pages
    is filled from `/explore/family_names` as the user types, so the names never appear
    in the page source and the markup test above cannot see them - but they still reach
    `autocomplete.js`, and it still writes them into innerHTML and into a data-label
    attribute."""
    as_role("admin")

    response = client.get(f"{FAMILY_NAMES_URL}?q=")

    assert response.status_code == 200
    items = response.get_json()["autocomplete_items"]
    assert items, "the endpoint answered no suggestions - nothing is being asserted"
    seen = set()
    for item in items:
        assert set(item) == {"label", "value"}, item
        for value in item.values():
            for character in MARKUP_CHARACTERS:
                assert character not in value, (
                    f"the endpoint hands the type-ahead {value!r}, which still carries "
                    f"{character!r} - the widget reads it as markup"
                )
            seen.add(value)
    for payload in PAYLOADS:
        assert str(escape(payload)) in seen, (
            f"the poisoned family name {payload!r} never reached the endpoint - the "
            "test is not exercising what it claims to"
        )


def test_both_producers_build_the_same_items():
    """The filter and the endpoint have to escape identically, or one call site is
    protected and the other only looks it. They call one function; this says so."""
    from mcritweb.autocomplete import RESPONSE_KEY, autocomplete_items

    names = list(PAYLOADS) + [ENTITY_NAME]

    assert autocomplete_items(names) == [
        {"label": str(escape(name)), "value": str(escape(name))} for name in names
    ]
    assert RESPONSE_KEY == "autocomplete_items", (
        "the ratchet recognises the fetched items by this key - renaming it here "
        "without renaming RESPONSE_FIELD would silence the lint"
    )


@pytest.mark.parametrize("path", [page for page in TYPE_AHEAD_PAGES
                                  if page not in SHIPPED_TYPE_AHEAD_PAGES])
def test_a_fetching_page_ships_no_names_of_its_own(client, as_role, poisoned_backend, path):
    """And the pages that fetch must not also embed the list: two producers on one page
    is the shape where one of them quietly stops being escaped.

    Scoped to the type-ahead's own script blocks. The family names are of course on
    these pages - they are listings of families - and the point here is only that the
    widget is not also handed a copy from the markup.
    """
    as_role("admin")

    markup = client.get(path).data.decode()

    assert FAMILY_NAMES_URL in markup, f"{path} does not fetch its suggestions"
    for script in autocomplete_scripts(markup):
        for payload in PAYLOADS:
            assert payload not in script and str(escape(payload)) not in script, (
                f"{path} still ships the family names it also fetches"
            )


# --- the ratchet ------------------------------------------------------------------

#: Comments are stripped first, or the lint is satisfied by prose: the filter's own
#: name appears in the explanatory comment above each call site, so a copied-then-
#: broken call site used to pass on the strength of the comment it was copied with.
JINJA_COMMENT = re.compile(r"\{#.*?#\}", re.DOTALL)
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT = re.compile(r"^[ \t]*//.*$", re.MULTILINE)

#: `data:` inside a `new Autocomplete(...)` options object, and the argument of any
#: `.setData(...)` call - the two ways data reaches the widget. `setData` is matched
#: with its dot so the vendored method *definition* is not taken for a call.
DATA_OPTION = re.compile(r"new\s+Autocomplete\s*\((?:[^()]|\([^()]*\))*?\bdata\s*:\s*([^,\n}]+)")
SET_DATA = re.compile(r"\.setData\s*\(\s*([^,\n)]+)")

#: A name bound to a filtered expression: `var families_ac = {{ x|autocomplete_items|tojson }}`.
FILTERED_BINDING = re.compile(
    r"(?:var|let|const)?\s*([A-Za-z_$][\w$]*)\s*=\s*\{\{[^{}]*\|\s*autocomplete_items\b"
)

#: The expression itself being a filtered Jinja expression, passed inline.
FILTERED_EXPRESSION = re.compile(r"\{\{[^{}]*\|\s*autocomplete_items\b")

#: The other producer of the same items, which arrived when issue #77 made the family
#: type-ahead fetch its suggestions as they are typed rather than shipping them with
#: the page: `explore.family_names` answers with them under the key
#: `autocomplete_items`, built by the function the filter itself delegates to
#: (`mcritweb/autocomplete.py`).
#:
#: Recognised by that field name and nothing else, so this is not a way around the
#: lint: a response read under any other key, or names turned into {label, value} in
#: the browser, is still flagged - both are in RATCHET_BYPASSES below. The name only
#: means anything because `test_the_endpoint_escapes_what_it_hands_the_type_ahead`
#: says the endpoint escapes and
#: `test_both_producers_build_the_same_items` says the two producers cannot drift.
RESPONSE_FIELD = re.compile(r"^[A-Za-z_$][\w$]*\.autocomplete_items\b")

#: An empty array literal: the initial `data:` of a widget that is filled in later,
#: which carries no names at all.
EMPTY_LITERAL = re.compile(r"^\[\s*\]$")


def strip_comments(source):
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", JINJA_COMMENT.sub("", source)))


def unfiltered_data_expressions(source):
    """The expressions in one file that reach the widget without going through the
    filter. Split out from the walk so the lint's own regression test can drive it."""
    stripped = strip_comments(source)
    safe_names = set(FILTERED_BINDING.findall(stripped))
    for pattern in (DATA_OPTION, SET_DATA):
        for match in pattern.finditer(stripped):
            expression = match.group(1).strip()
            if (FILTERED_EXPRESSION.search(expression)
                    or expression in safe_names
                    or RESPONSE_FIELD.match(expression)
                    or EMPTY_LITERAL.match(expression)):
                continue
            yield stripped.count("\n", 0, match.start()) + 1, expression


def front_end_sources():
    """Templates and scripts that name the widget.

    Scanning `static/` matters - a `new Autocomplete(` there would otherwise be
    invisible - but `setData` is a name other libraries use for something else
    entirely: SortableJS calls `dataTransfer.setData("Text", ...)` eight times. A file
    that never mentions `Autocomplete` cannot be feeding one, and that test is
    self-maintaining, where a list of vendored filenames to skip is the exception list
    AGENTS.md warns grows back. The vendored widget is skipped explicitly: it *defines*
    `setData` rather than calling one, and it is not ours to lint either way.
    """
    for root, suffix in ((TEMPLATE_ROOT, ".html"), (STATIC_ROOT, ".js")):
        for directory, _, filenames in os.walk(root):
            for filename in sorted(filenames):
                if not filename.endswith(suffix):
                    continue
                path = os.path.join(directory, filename)
                if os.path.abspath(path) == os.path.join(STATIC_ROOT, "autocomplete.js"):
                    continue
                with open(path, encoding="utf-8") as handle:
                    source = handle.read()
                if "Autocomplete" in source:
                    yield path, source


def test_every_type_ahead_builds_its_data_through_the_escaping_filter():
    """A ratchet, in the shape of `testScriptEscaping.py`'s.

    The escaping lives at the call sites because `static/autocomplete.js` is vendored
    and may not be patched, which means a third call site added without it reopens the
    hole in full. The browser test below only knows the pages that exist today.

    This resolves the data *expression* - a bare name has to be bound to a filtered
    expression somewhere in the same file - rather than asking whether the filter's
    name appears anywhere in the block, which a comment satisfies. It covers
    `setData` as well as the constructor, and `static/*.js` as well as the templates.
    What it cannot follow is data built in one file and consumed in another; nothing
    does that today.
    """
    offenders = []
    for path, source in front_end_sources():
        relative = os.path.relpath(path, PACKAGE_ROOT).replace(os.sep, "/")
        for line, expression in unfiltered_data_expressions(source):
            offenders.append(f"{relative}:{line} ({expression})")
    offenders.sort()

    assert not offenders, (
        "a type-ahead is built from data the escaping filter did not produce, at: "
        + ", ".join(offenders) + ". autocomplete.js renders each suggestion through "
        "innerHTML and into a data-label attribute, so pass the names through "
        "|autocomplete_items - |tojson only protects the transport."
    )


#: Each of these passed the ratchet's first version. They are the review findings
#: turned into cases, so the lint cannot quietly regress to a substring search.
RATCHET_BYPASSES = {
    "a comment naming the filter": (
        "<script>\n// built with |autocomplete_items\n"
        "var ac_data = {{ families|tojson }};\n"
        "new Autocomplete(field, {data: ac_data, threshold: 1});\n</script>"
    ),
    "setData with raw names": (
        "<script>\nvar ok = {{ families|autocomplete_items|tojson }};\n"
        "new Autocomplete(field, {data: ok});\nac.setData(rawFamilies);\n</script>"
    ),
    "built in one block, consumed in another": (
        "<script>\nvar d = {{ families|tojson }};\n</script>\n"
        "<script>\nnew Autocomplete(field, {data: d});\n</script>"
    ),
}

#: And these must stay quiet, or the ratchet is just noise.
RATCHET_ACCEPTS = {
    "inline filtered expression": (
        "<script>\nnew Autocomplete(field, {data: {{ families|autocomplete_items|tojson }}});\n</script>"
    ),
    "filtered binding, used later": (
        "<script>\nvar families_ac = {{ family_names|autocomplete_items|tojson }};\n"
        "new Autocomplete(field, {data: families_ac, maximumItems: 5});\n"
        "families_ac.push;\nac.setData(families_ac);\n</script>"
    ),
}


@pytest.mark.parametrize("description", sorted(RATCHET_BYPASSES))
def test_the_ratchet_rejects_the_ways_around_it(description):
    findings = list(unfiltered_data_expressions(RATCHET_BYPASSES[description]))
    assert findings, f"the ratchet still lets through: {description}"


@pytest.mark.parametrize("description", sorted(RATCHET_ACCEPTS))
def test_the_ratchet_accepts_a_correct_call_site(description):
    findings = list(unfiltered_data_expressions(RATCHET_ACCEPTS[description]))
    assert not findings, f"the ratchet wrongly flags: {description} -> {findings}"


# --- the browser ------------------------------------------------------------------

def session_cookie_value(app, user_id):
    """A signed session cookie for a browser, matching what `as_role` sets on the
    test client."""
    from flask.sessions import SecureCookieSessionInterface

    serializer = SecureCookieSessionInterface().get_signing_serializer(app)
    return serializer.dumps({"user_id": user_id})


@pytest.fixture
def live_url(app):
    """The app on a real socket. Playwright needs one; the test client is not a server."""
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.port}"
    finally:
        server.shutdown()
        thread.join(timeout=10)


#: Read back after the widget has rendered. `textContent` rather than `innerText`
#: because the dropdown may be hidden, and a hidden element has no inner text.
#: `getAttributeNames` is what catches an attribute break - an injected handler is a
#: real attribute on the button, and no amount of reading its text would show it.
MENU_SNAPSHOT = """
(selector) => {
  const field = document.querySelector(selector);
  const menu = field.nextSibling;
  const items = [...menu.querySelectorAll('.dropdown-item')];
  return {
    texts: items.map(item => item.textContent),
    labels: items.map(item => item.getAttribute('data-label')),
    values: items.map(item => item.getAttribute('data-value')),
    attributes: items.map(item => item.getAttributeNames().join(',')),
    elements: menu.querySelectorAll('*:not(.dropdown-item):not(span)').length,
    highlights: menu.querySelectorAll('.dropdown-item span.text-primary').length,
  };
}
"""

TYPE_INTO_FIELD = """
([selector, lookup]) => {
  const field = document.querySelector(selector);
  field.value = lookup;
  field.dispatchEvent(new Event('input'));
}
"""

HAS_SUGGESTION = """
([selector, wanted]) => {
  const field = document.querySelector(selector);
  const menu = field && field.nextSibling;
  return !!menu && menu.querySelectorAll('.dropdown-item').length >= wanted;
}
"""

#: Selecting a suggestion must hand back the *original* name, not the escaped one:
#: the widget reads `data-label` off the button, and the browser decoded the entities
#: when it parsed that attribute. The click is dispatched on the button rather than on
#: the highlight span because the vendored widget reads `e.target` - clicking the
#: highlighted characters themselves loses the label, which is an upstream bug and not
#: this one.
SELECT_FIRST_SUGGESTION = """
(selector) => {
  const field = document.querySelector(selector);
  field.nextSibling.querySelector('.dropdown-item').click();
  return field.value;
}
"""


def drive_type_ahead(sync_api, app, live_url, user_id, path, lookup, expected_items):
    """Open `path` in a browser, type `lookup`, and report what the widget rendered."""
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:  # noqa: BLE001 - a missing browser is a skip, not a failure
            pytest.skip(f"playwright has no chromium installed: {exc}")
        try:
            context = browser.new_context()
            context.add_cookies([{
                "name": "session",
                "value": session_cookie_value(app, user_id),
                "url": live_url,
            }])
            page = context.new_page()
            page.goto(live_url + path)
            page.wait_for_selector(FIELD_SELECTOR, state="attached", timeout=15000)

            page.evaluate(TYPE_INTO_FIELD, [FIELD_SELECTOR, lookup])
            page.wait_for_function(HAS_SUGGESTION, arg=[FIELD_SELECTOR, expected_items], timeout=10000)

            executed = True
            try:
                page.wait_for_function("() => window.__pwned !== undefined", timeout=2000)
            except sync_api.TimeoutError:
                executed = False

            snapshot = page.evaluate(MENU_SNAPSHOT, FIELD_SELECTOR)
            snapshot["executed"] = executed
            snapshot["selected"] = page.evaluate(SELECT_FIRST_SUGGESTION, FIELD_SELECTOR)
            return snapshot
        finally:
            browser.close()


@pytest.mark.parametrize("path", BROWSER_PAGES)
def test_a_family_name_cannot_execute_in_the_type_ahead(app, poisoned_backend, live_url, make_user, path):
    sync_api = pytest.importorskip("playwright.sync_api")
    user_id = make_user("admin")
    rendered = drive_type_ahead(sync_api, app, live_url, user_id, path, LOOKUP, len(PAYLOADS))

    assert not rendered["executed"], (
        f"a crafted family name executed from the type-ahead on {path}: typing "
        f"{LOOKUP!r} ran a payload's handler"
    )
    assert rendered["elements"] == 0, (
        f"the type-ahead on {path} turned a family name into {rendered['elements']} "
        f"element(s) instead of text"
    )
    for item_attributes in rendered["attributes"]:
        assert "onmouseover" not in item_attributes, (
            f"a family name injected an event handler attribute on {path}: "
            f"{item_attributes}"
        )
    for payload in PAYLOADS:
        assert payload in rendered["texts"], (
            f"the suggestion for {payload!r} on {path} does not read as text - "
            f"got {rendered['texts']}"
        )
        assert payload in rendered["labels"], (
            f"data-label for {payload!r} on {path} does not round-trip - "
            f"got {rendered['labels']}"
        )
        assert payload in rendered["values"], (
            f"data-value for {payload!r} on {path} does not round-trip - "
            f"got {rendered['values']}"
        )
    assert rendered["highlights"] >= len(PAYLOADS), (
        f"the typed prefix is no longer highlighted on {path} - escaping the data must "
        f"not cost the widget its highlightTyped behaviour"
    )
    assert rendered["selected"] in PAYLOADS, (
        f"selecting the suggestion on {path} put {rendered['selected']!r} in the field "
        f"instead of the family name - the escaping has to be invisible on the way out"
    )


def test_the_highlighter_severs_an_entity(app, poisoned_backend, live_url, make_user):
    """The documented cost of escaping at the call site, pinned so it stays measured.

    `autocomplete.js:70-77` finds the lookup in the escaped label and slices that same
    escaped string at the offsets it found, injecting the highlight `<span>` between
    them. A lookup ending inside an entity therefore cuts the entity in half, and the
    two fragments render as the literal `&amp;` rather than as `&`.

    Everything that matters for security still holds and is asserted here; only the
    visible text is wrong, and only for a name containing one of the five escaped
    characters. It cannot be fixed from the call site - `item.label` is one value, and
    the matcher, the highlighter and the attribute all read it - so it is recorded
    rather than argued away in a comment. If the severing ever stops, this test says
    so, and the caveat in AGENTS.md needs deleting with it.
    """
    sync_api = pytest.importorskip("playwright.sync_api")
    user_id = make_user("admin")
    rendered = drive_type_ahead(
        sync_api, app, live_url, user_id, "/explore/families", ENTITY_LOOKUP, 1
    )

    assert not rendered["executed"], "the entity case must still be inert"
    assert rendered["elements"] == 0, "the entity case must not produce elements"
    assert ENTITY_NAME in rendered["labels"], (
        f"data-label must round-trip even when the highlighter severs the entity - "
        f"got {rendered['labels']}"
    )
    assert rendered["selected"] == ENTITY_NAME, (
        f"selecting must still yield the original name - got {rendered['selected']!r}"
    )

    assert ENTITY_NAME not in rendered["texts"], (
        "the highlighter no longer severs entities - the widget was replaced or "
        "patched, so drop this test and the caveat in AGENTS.md"
    )
    assert "R&amp;D" in rendered["texts"], (
        f"expected the severed entity to render literally - got {rendered['texts']}"
    )
