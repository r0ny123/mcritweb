#!/usr/bin/python
"""No script in this repository's own markup assigns to an undeclared name.

An assignment with no `var`, `let` or `const` creates a property on `window`. Two
pages, or two script blocks on one page, then share a variable neither of them meant
to - and `families_ac` and `myDropzone` really are written from two different blocks
that land on the same page. Issue #61.

This is a ratchet: the list below is empty and may only stay empty. Adding a name to
it is a regression, not a note.

Scope is deliberately this repository's own JavaScript - the inline blocks in
`templates/` and `static/post_action.js`. The vendored libraries under `static/`
(jQuery, DataTables, Dropzone, ...) carry their own licences and are not ours to
reformat; see AGENTS.md.
"""

import logging
import pathlib
import re
import unittest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

ROOT = pathlib.Path(__file__).resolve().parents[1] / "mcritweb"

#: Names that are properties of the browser or of a library, not variables of ours.
NOT_OURS = {"window", "document", "this", "self"}

#: An assignment that starts a line: `name = value`, but not `name == value`,
#: `name => ...`, `a.name = ...` (the regex is anchored) or `name: value`.
ASSIGNMENT = re.compile(r"^\s*([A-Za-z_$][\w$]*)\s*=\s*(?![=>])")


def javascript_sources():
    """(label, text) for every piece of JavaScript this repository wrote."""
    for path in sorted((ROOT / "templates").rglob("*.html")):
        text = path.read_text()
        in_script = False
        block = []
        for number, line in enumerate(text.splitlines(), 1):
            lowered = line.lower()
            if "</script" in lowered:
                in_script = False
                continue
            if in_script:
                block.append((number, line))
            if "<script" in lowered and "src=" not in lowered:
                in_script = True
        if block:
            yield path, text, block

    post_action = ROOT / "static" / "post_action.js"
    text = post_action.read_text()
    yield post_action, text, list(enumerate(text.splitlines(), 1))


def is_declared(name, text):
    return bool(
        re.search(rf"\b(?:var|let|const|function|class)\s+{re.escape(name)}\b", text)
        # a function parameter, including an arrow function's
        or re.search(rf"function\s*\w*\s*\([^)]*\b{re.escape(name)}\b[^)]*\)", text)
        or re.search(rf"\(\s*[^)]*\b{re.escape(name)}\b[^)]*\)\s*=>", text)
        or re.search(rf"\b{re.escape(name)}\s*=>", text)
        # `for (name in ...)` / `for (name of ...)`
        or re.search(rf"for\s*\(\s*{re.escape(name)}\s+(?:in|of)\b", text)
    )


def undeclared_assignments():
    findings = []
    for path, text, block in javascript_sources():
        for number, line in block:
            match = ASSIGNMENT.match(line)
            if not match:
                continue
            name = match.group(1)
            if name in NOT_OURS or is_declared(name, text):
                continue
            findings.append(f"{path.relative_to(ROOT.parent)}:{number}: {line.strip()}")
    return findings


def test_nothing_assigns_to_an_undeclared_name():
    findings = undeclared_assignments()

    assert findings == [], "undeclared assignment(s):\n" + "\n".join(findings)


def test_the_scanner_reads_something():
    """A scanner that silently matches no files would pass forever."""
    sources = list(javascript_sources())

    assert len(sources) > 5, f"only found {len(sources)} sources of JavaScript"


def test_the_scanner_would_catch_one():
    """And a scanner that cannot fail is not a ratchet."""
    text = "function f() {\n  leaked = 1;\n}"

    assert not is_declared("leaked", text)
    assert ASSIGNMENT.match("  leaked = 1;")


def test_the_scanner_does_not_flag_ordinary_code():
    for line, text in [
        ("  const x = 1;", "const x = 1;"),
        ("  x = 1;", "let x;"),
        ("  x = 1;", "function g(x) {}"),
        ("  i = 1;", "for (i of things) {}"),
    ]:
        match = ASSIGNMENT.match(line)
        name = match.group(1) if match else None
        assert name is None or is_declared(name, text), f"{line!r} against {text!r}"


if __name__ == "__main__":
    unittest.main()
