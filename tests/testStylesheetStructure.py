#!/usr/bin/python
"""The project's own stylesheets parse the way they read.

A dropped `}` does not break CSS - it reparents. Every rule after it becomes a rule
*inside* whatever block was left open, so `static/style.css` losing one brace anywhere
above `:root[data-theme="dark"]` puts the rest of the file inside the dark palette and
the light theme quietly stops being styled. Nothing raises, no page 500s, no test that
renders markup can see it, and `ruff` does not read CSS.

That is a merge hazard rather than an editing hazard: `style.css` grew rules from
several changes at once - the nowrap rules for headings and action cells (#52), the
diagram placeholder (#68), the whole tokenised palette and its dark counterpart (#70) -
and several of those landed at the end of the file, which is exactly where a
three-way merge is most likely to lose a closing brace between two additions.

Two assertions per file, because balance alone is not enough: a file can balance and
still be wrong if a top-level block ended up nested. `:root` and `@media` are written
at column 0 in all four files, and a `:root` that has become indented is a `:root`
inside something.

Vendored stylesheets are not checked - they are not ours to fix, and Bootstrap's
minified build is one line.
"""

import pathlib
import re

import pytest

STATIC = pathlib.Path(__file__).resolve().parent.parent / "mcritweb" / "static"

#: the project's own stylesheets. `theme-dark.css` is the one that would swallow the
#: rest of the file; the other three are here because the same accident applies to any
#: of them and the check costs nothing.
OURS = ("style.css", "theme-dark.css", "navbar.css", "signin.css")

COMMENT = re.compile(r"/\*.*?\*/", re.S)
STRING = re.compile(r'"(?:[^"\\]|\\.)*"' + r"|'(?:[^'\\]|\\.)*'")

#: a `:root` or `@media` that is not at column 0 - i.e. one that has ended up inside
#: another block.
NESTED_TOP_LEVEL = re.compile(r"(?m)^[ \t]+(?::root|@media)[^{]*\{")


def without_comments_and_strings(text):
    """Braces inside a comment or a string are not structure.

    `content: "rendering diagram\\2026"` and `url("...")` both carry characters this
    would otherwise count.
    """
    return STRING.sub('""', COMMENT.sub("", text))


def brace_depth(text):
    """(final depth, line of the first unmatched `}`) for one stylesheet."""
    depth, line, first_extra = 0, 1, None
    for character in text:
        if character == "\n":
            line += 1
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth < 0 and first_extra is None:
                first_extra = line
    return depth, first_extra


@pytest.mark.parametrize("name", OURS)
def test_the_stylesheet_braces_balance(name):
    depth, first_extra = brace_depth(without_comments_and_strings((STATIC / name).read_text(encoding="utf-8")))

    assert first_extra is None, (
        f"{name} closes a block that was never opened, at line {first_extra} - "
        "every rule from there on has been reparented"
    )
    assert depth == 0, (
        f"{name} ends {depth} block(s) deep: a closing brace is missing, so the rules "
        "after it are nested inside whatever is still open rather than applying on "
        "their own"
    )


@pytest.mark.parametrize("name", OURS)
def test_no_palette_block_has_been_nested(name):
    nested = NESTED_TOP_LEVEL.findall(without_comments_and_strings((STATIC / name).read_text(encoding="utf-8")))

    assert not nested, (
        f"{name} has a :root or @media block that is not at the top level: "
        f"{[block.strip() for block in nested]}. A palette declared inside another "
        "rule applies to that rule's subtree only, which is not what any of these mean."
    )


def test_the_dark_palette_only_redefines_names():
    """`style.css` ends with the dark palette, and it has to stay a palette.

    This is what a lost brace above it looks like from the other side: the block fills
    up with the rules that used to follow it. It declares custom properties and
    `color-scheme` and nothing else, so anything else in it is something that fell in.
    """
    # not through `without_comments_and_strings` - that blanks `"dark"` out of the
    # selector along with every other quoted run. There is no brace inside this block.
    text = COMMENT.sub("", (STATIC / "style.css").read_text(encoding="utf-8"))
    start = text.index(':root[data-theme="dark"]')
    block = text[text.index("{", start) + 1:]
    block = block[:block.index("}")]

    stray = [line.strip() for line in block.splitlines()
             if line.strip() and not line.strip().startswith("--")
             and not line.strip().startswith("color-scheme:")]

    assert not stray, f"the dark palette block has picked up: {stray}"


#: The two ways the structure can be broken, as text, so the checks above cannot
#: quietly stop checking. Written as whole little stylesheets rather than by mutating
#: the real file, which would leave it damaged if the test failed halfway.
BROKEN = {
    "a dropped closing brace": ":root {\n  --a: red;\n\nhtml {\n  color: var(--a);\n}\n",
    "one closing brace too many": ":root {\n  --a: red;\n}\n}\nhtml { color: red; }\n",
}


@pytest.mark.parametrize("description", sorted(BROKEN))
def test_the_check_sees_a_broken_stylesheet(description):
    depth, first_extra = brace_depth(without_comments_and_strings(BROKEN[description]))

    assert depth != 0 or first_extra is not None, f"the brace check misses: {description}"


def test_a_brace_in_a_comment_or_a_string_is_not_structure():
    """The other direction: this must not fail on a correct file."""
    text = '/* } */\n:root {\n  content: "{";\n}\n'

    assert brace_depth(without_comments_and_strings(text)) == (0, None)
