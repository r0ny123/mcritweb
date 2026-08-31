#!/usr/bin/python
"""The supported Python version is stated in four places. They have to agree.

`README.md` told readers "Python 3.8+" while CI tested 3.11 upwards, `ruff.toml` linted
against py311, and every `mcrit` release this project can install - the pin is
`mcrit>=1.5.3`, and 1.5.3 is the first to declare it - requires `>=3.11`.

The dependency graph makes 3.8 unusable rather than merely untested: pip on 3.10 finds
no satisfiable `mcrit` at all. Without a `python_requires`, what the reader gets for
following the README is a resolver error about `mcrit`, which names neither Python nor
the version they need. Declaring the floor turns that into the sentence pip exists to
print.

These tests read the four sources rather than restating them, so the next bump has to
move all four together or fail here.
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
FLOOR = (3, 11)


def _version(text):
    return tuple(int(part) for part in text.split("."))


def test_setup_py_declares_the_floor():
    match = re.search(r'python_requires\s*=\s*"\s*>=\s*([\d.]+)"', (ROOT / "setup.py").read_text())
    assert match, "setup.py declares no python_requires, so pip cannot say what is wrong"
    assert _version(match.group(1)) == FLOOR


def test_the_readme_does_not_promise_a_version_that_cannot_work():
    readme = (ROOT / "README.md").read_text(encoding="utf8")
    promises = re.findall(r"Python (\d+\.\d+)\+", readme)

    assert promises, "the README no longer states a Python version at all"
    for promised in promises:
        assert _version(promised) >= FLOOR, \
            f"README offers Python {promised}+, which cannot install mcrit"


def test_ruff_lints_against_the_version_that_is_supported():
    match = re.search(r'target-version\s*=\s*"py(\d)(\d+)"', (ROOT / "ruff.toml").read_text())
    assert match, "ruff.toml sets no target-version"
    assert (int(match.group(1)), int(match.group(2))) == FLOOR


def test_ci_runs_the_oldest_version_that_is_promised():
    """A floor nothing tests is a guess. The lowest entry of the matrix is the only
    evidence that the oldest supported version actually works.

    Read with a regex rather than a YAML parser: pyyaml is not a dependency of this
    project, and adding one so that a test can read one line would be a poor trade.
    """
    workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(encoding="utf8")
    matrices = re.findall(r"python-version:\s*\[([^\]]+)\]", workflow)

    assert matrices, "no job pins a python-version matrix"
    for entry in matrices:
        versions = re.findall(r"\d+\.\d+", entry)
        assert versions, f"could not read any version out of {entry!r}"
        assert min(_version(v) for v in versions) == FLOOR


def test_every_installable_mcrit_needs_this_floor():
    """The floor is not a preference, it is inherited. Stated here so that relaxing it
    is visibly a claim about mcrit, not about this repository alone."""
    setup = (ROOT / "setup.py").read_text()
    match = re.search(r'"mcrit>=([\d.]+)"', setup)

    assert match, "the mcrit pin moved; re-check what Python that release requires"
    assert _version(match.group(1)) >= (1, 5, 3), \
        "mcrit 1.5.3 is the oldest release known to require Python >=3.11 - a lower pin " \
        "would allow a release with a different floor, and this file would be guessing"


if __name__ == "__main__":
    pytest.main([__file__])
