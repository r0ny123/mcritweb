#!/usr/bin/python
"""A start tag's closing `>` must not depend on a template condition.

Thirteen check/cross icons were written as

    <i {% if flag %} class="fa-solid fa-square-check" {% else %} class="fa-solid fa-times-circle"> {% endif %}</i>

with the tag's `>` inside the else branch. A false flag renders an ordinary icon. A true
one leaves the start tag without an end of its own, so an HTML parser reads the `</i`
that follows as two more attributes on it (`<` and `i`): the icon element is never
closed, and nothing on the page looks wrong enough to say so.

Two tests with different reach, as in testScriptEscaping. The lint walks the template
tree, which is what keeps the pattern out of templates no test renders. The render is
the bug as a browser meets it, through a row macro every listing uses.
"""

import copy
import logging
import os
import re
import unittest
from html.parser import HTMLParser

import pytest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

PACKAGE_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcritweb")
TEMPLATE_ROOT = os.path.join(PACKAGE_ROOT, "templates")

#: An if/else/endif with no other block tag inside it - the shape an attribute switch
#: takes. The branches are captured so their markup can be compared.
CONDITIONAL = re.compile(
    r"\{%-?\s*if\b(?:(?!%\}).)*%\}(?P<yes>(?:(?!\{%).)*)"
    r"\{%-?\s*else\s*-?%\}(?P<no>(?:(?!\{%).)*)"
    r"\{%-?\s*endif\s*-?%\}",
    re.DOTALL,
)
#: Jinja's own delimiters. They are blanked out before looking for markup, since the `>`
#: in `{{ a > b }}` is a comparison and not the end of a tag.
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.DOTALL)


@pytest.fixture
def fake_mcrit(corpus_mcrit):
    return corpus_mcrit


def template_files():
    for directory, _, filenames in os.walk(TEMPLATE_ROOT):
        for filename in sorted(filenames):
            if filename.endswith(".html"):
                yield os.path.join(directory, filename)


def blank_jinja(source):
    """The source with every Jinja delimiter pair replaced by spaces of the same length,
    so offsets into it are offsets into the source."""
    return JINJA.sub(lambda match: " " * len(match.group()), source)


def tags_closed_by_one_branch():
    """Every conditional inside a start tag whose branches disagree about closing it, as
    `path:line` strings."""
    for path in sorted(template_files()):
        with open(path, encoding="utf-8") as template:
            source = template.read()
        markup = blank_jinja(source)
        relative = os.path.relpath(path, TEMPLATE_ROOT)
        for match in CONDITIONAL.finditer(source):
            before = markup[:match.start()]
            if before.rfind("<") < before.rfind(">"):
                # not inside a tag - a conditional between elements may open and close
                # whatever it likes
                continue
            yes = markup[match.start("yes"):match.end("yes")]
            no = markup[match.start("no"):match.end("no")]
            if (">" in yes) != (">" in no):
                yield f"{relative}:{source.count(chr(10), 0, match.start()) + 1}"


def test_no_start_tag_is_closed_by_only_one_branch_of_a_condition():
    assert list(tags_closed_by_one_branch()) == []


def test_the_lint_finds_the_pattern_it_is_for():
    """Against the markup the icons had, so a lint that matches nothing cannot pass."""
    broken = '<td><i {% if flag %} class="fa-solid fa-square-check" {% else %} class="fa-solid fa-times-circle"> {% endif %}</i></td>'
    fixed = '<td><i {% if flag %} class="fa-solid fa-square-check" {% else %} class="fa-solid fa-times-circle" {% endif %}></i></td>'
    between_elements = '<td>{% if flag %}<b>yes</b>{% else %}no{% endif %}</td>'

    def closed_by_one_branch(source):
        markup = blank_jinja(source)
        for match in CONDITIONAL.finditer(source):
            before = markup[:match.start()]
            yes = markup[match.start("yes"):match.end("yes")]
            no = markup[match.start("no"):match.end("no")]
            if before.rfind("<") > before.rfind(">") and (">" in yes) != (">" in no):
                return True
        return False

    assert closed_by_one_branch(broken)
    assert not closed_by_one_branch(fixed)
    assert not closed_by_one_branch(between_elements)


class IconTags(HTMLParser):
    """How many `<i>` elements a fragment leaves open, and any attribute names a
    well-formed tag cannot have."""

    def __init__(self):
        super().__init__()
        self.open = 0
        self.stray_attributes = []

    def handle_starttag(self, tag, attrs):
        if tag == "i":
            self.open += 1
            self.stray_attributes += [name for name, _ in attrs if not re.fullmatch(r"[a-z][a-z0-9-]*", name)]

    def handle_endtag(self, tag):
        if tag == "i":
            self.open -= 1


@pytest.mark.parametrize("is_library", [True, False], ids=["library", "not-a-library"])
def test_the_library_icon_of_a_sample_row_is_closed(app, fake_mcrit, is_library):
    """The library column is on by default in every sample listing. It was the true
    branch - a library sample - that left its icon open."""
    sample = copy.copy(next(iter(fake_mcrit._samples.values())))
    sample.is_library = is_library
    source = "{% from 'table/table.html' import sample_table %}{{ sample_table([sample]) }}"
    with app.test_request_context("/"):
        rendered = app.jinja_env.from_string(source).render(sample=sample)

    icons = IconTags()
    icons.feed(rendered)
    icons.close()

    expected_icon = "fa-square-check" if is_library else "fa-times-circle"
    assert expected_icon in rendered, "the library cell is not in the rendered row"
    assert icons.stray_attributes == []
    assert icons.open == 0


if __name__ == "__main__":
    unittest.main()
