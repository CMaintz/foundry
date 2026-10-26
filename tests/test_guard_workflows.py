"""The default `ruleset_paths` regex in the reusable workflows: what a bundled
ruleset+source PR must justify with the ruleset-change label."""

import re
from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def ruleset_default(name):
    text = (WORKFLOWS / name).read_text(encoding="utf-8")
    block = text.split("ruleset_paths:", 1)[1]
    return re.search(r"default: '([^']*)'", block).group(1)


def test_security_and_guards_share_one_default():
    # security.yml passes its own default through to _guards.yml, so an edit to only
    # one of them silently changes what consumers of the other are guarded on.
    assert ruleset_default("security.yml") == ruleset_default("_guards.yml")


@pytest.mark.parametrize(
    "path",
    [
        "vite.config.ts",
        "packages/a/vitest.config.mts",
        "web/jest.config.js",
        ".coveragerc",
        "backend/.coveragerc",
        "codecov.yml",
        "phpunit.xml.dist",
        "api/phpunit.xml",
        "tests/coverage.runsettings",
        "flaky-baseline.json",
        "services/a/flaky-baseline.json",
    ],
)
def test_coverage_configs_and_flaky_baseline_are_ruleset_paths(path):
    assert re.search(ruleset_default("_guards.yml"), path)


@pytest.mark.parametrize("path", ["src/vite.ts", "docs/coverage.md", "src/flaky.json"])
def test_lookalike_source_files_are_not_ruleset_paths(path):
    assert not re.search(ruleset_default("_guards.yml"), path)
