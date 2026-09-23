#!/usr/bin/python
"""A reference to an ADR has to reach the ADR it means.

The ADRs were renumbered while their branches waited to land - 0003 was claimed three
times over - and the references did not follow. AGENTS.md linked 0014 and 0010 under
the text "ADR-0003", and two comments sent the reader to 0003, which is about function
labels, for the CFG export round trip that 0011 records. Nothing failed: a number that
has moved still names *some* ADR.

So a reference names the file, and three checks hold it to that:

- a path into docs/adr has to exist. A path cut short at the number goes on resolving
  after a renumber; the file name does not, so the next renumber fails here;
- a link's text has to carry the number of the file it links to;
- a bare "ADR-NNNN" has to be the number of an ADR that exists.
"""

import logging
import os
import re
import unittest

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)-15s %(message)s")
logging.disable(logging.CRITICAL)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADR_ROOT = os.path.join(REPO_ROOT, "docs", "adr")
ADR_FILE = re.compile(r"(?P<number>\d{4})-[a-z0-9-]+\.md")

#: Where references are written: the markdown at the root and under docs/, and the
#: comments and docstrings of the application and its tests.
SEARCHED = (("", (".md",), False), ("docs", (".md",), True), ("mcritweb", (".py", ".html"), True), ("tests", (".py",), True))

#: A path into docs/adr, up to the first character a file name cannot hold.
ADR_PATH = re.compile(r"docs/adr/[A-Za-z0-9._-]*")
#: A markdown link whose text names an ADR by number.
ADR_LINK = re.compile(r"\[ADR[- ](?P<number>\d{4})\]\((?P<target>[^)\s]+)\)")
#: An ADR named by number outside a link's text.
ADR_NUMBER = re.compile(r"(?<!\[)\bADR[- ](?P<number>\d{4})\b")


def adr_numbers():
    return {match.group("number") for match in map(ADR_FILE.fullmatch, os.listdir(ADR_ROOT)) if match}


def searched_files():
    for directory, suffixes, recursive in SEARCHED:
        root = os.path.join(REPO_ROOT, directory)
        for current, subdirectories, filenames in os.walk(root):
            subdirectories[:] = [name for name in subdirectories if not name.startswith(".") and name != "__pycache__"]
            for filename in sorted(filenames):
                path = os.path.join(current, filename)
                # this module quotes the broken references in its own docstring
                if filename.endswith(suffixes) and path != os.path.abspath(__file__):
                    yield path
            if not recursive:
                break


def occurrences(pattern):
    """(path, "relative/path:line", match) for every match of `pattern` in a searched file."""
    for path in searched_files():
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        relative = os.path.relpath(path, REPO_ROOT)
        for match in pattern.finditer(text):
            yield path, f"{relative}:{text.count(chr(10), 0, match.start()) + 1}", match


def test_every_path_into_docs_adr_exists():
    missing = [
        f"{where}: {match.group()}"
        for _, where, match in occurrences(ADR_PATH)
        # a sentence can end right after the file name
        if not os.path.exists(os.path.join(REPO_ROOT, match.group().rstrip(".")))
    ]
    assert missing == []


def test_a_link_to_an_adr_carries_the_number_of_the_file_it_reaches():
    wrong = []
    for path, where, match in occurrences(ADR_LINK):
        target = os.path.normpath(os.path.join(os.path.dirname(path), match.group("target")))
        named = ADR_FILE.fullmatch(os.path.basename(target))
        if not os.path.isfile(target) or named is None or named.group("number") != match.group("number"):
            wrong.append(f"{where}: {match.group()}")
    assert wrong == []


def test_an_adr_named_by_number_exists():
    known = adr_numbers()
    unknown = [f"{where}: {match.group()}" for _, where, match in occurrences(ADR_NUMBER) if match.group("number") not in known]
    assert unknown == []


def test_the_checks_see_the_references_they_are_for():
    """The searched tree does hold references of each kind, so none of the checks above
    can pass by finding nothing."""
    assert any(True for _ in occurrences(ADR_PATH))
    assert any(True for _ in occurrences(ADR_LINK))
    assert any(True for _ in occurrences(ADR_NUMBER))


if __name__ == "__main__":
    unittest.main()
