"""The rule catalog (presets/rules/) and scripts/foundry-explain: every rule Foundry turns
on or adds has an entry, every matcher points at a real entry and matches its own example,
and the CLI explains an id, a pasted log and the last failure in the telemetry.

Coverage scope (what "Foundry-enabled" means here): rules Foundry itself declares in its
presets, read from the files so a new one cannot ship without an entry. That is the rule
keys in presets/lint/eslint.config.mjs, the rules defined in presets/lint/pmd/no-var.xml,
the ruff families selected in presets/lint/ruff.toml, the smells with a Foundry-written
guide in presets/habit-hooks/java/guides/, the smells of every sensor a habit-hooks preset
tunes, and the labels ruleset-guard accepts. Upstream defaults Foundry does not touch
(the rest of habit-hooks' smells, eslint's recommended set) are out of scope: their
upstream docs and coaching text already explain them.
"""
import json
import os
import re
import subprocess
import sys
import tomllib
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "foundry-explain"
RULES = ROOT / "presets" / "rules"
PRESETS = ROOT / "presets"
# A tuned habit-hooks sensor -> the smells it reports. pmd's smells are covered by the
# Java guides; dotnet-build's ship only commented out in the preset. The javascript and
# typescript presets' eslint sensor reports the TS plugin's function-level smells (file
# length stays the line-count sensor's); the javascript preset's comment sensor is disabled
# and reports nothing in scope.
SENSOR_SMELLS = {
    "line-count": ["oversized-file"],
    "jscpd": ["duplicated-code"],
    "pmd": [],
    "eslint": ["oversized-function", "too-many-parameters", "high-complexity", "deep-nesting"],
    "comment": [],
}

_loader = SourceFileLoader("foundry_explain", str(SCRIPT))
_spec = spec_from_loader("foundry_explain", _loader)
explain = module_from_spec(_spec)
_loader.exec_module(explain)


def catalog_ids() -> set[str]:
    return {r["id"] for r in tomllib.loads((RULES / "catalog.toml").read_text(encoding="utf-8"))["rule"]}


def matchers() -> list[dict]:
    return tomllib.loads((RULES / "matchers.toml").read_text(encoding="utf-8"))["match"]


def eslint_rules() -> set[str]:
    text = (PRESETS / "lint" / "eslint.config.mjs").read_text(encoding="utf-8")
    block = text.split("rules:", 1)[1]
    return {f"eslint:{m}" for m in re.findall(r'^\s{6}"([^"]+)":', block, re.M)}


def pmd_rules() -> set[str]:
    text = (PRESETS / "lint" / "pmd" / "no-var.xml").read_text(encoding="utf-8")
    return {f"pmd:{m}" for m in re.findall(r'<rule name="(\w+)"', text)}


def ruff_families() -> set[str]:
    select = tomllib.loads((PRESETS / "lint" / "ruff.toml").read_text(encoding="utf-8"))["lint"]["select"]
    return {f"ruff:{f}" for f in select}


def tuned_sensor_smells() -> set[str]:
    smells = set()
    for preset in (PRESETS / "habit-hooks").glob("*.toml"):
        for sensor in tomllib.loads(preset.read_text(encoding="utf-8")).get("sensors", {}):
            assert sensor in SENSOR_SMELLS, f"{preset.name} tunes sensor {sensor!r}: map it in SENSOR_SMELLS"
            smells.update(SENSOR_SMELLS[sensor])
    guides = (PRESETS / "habit-hooks" / "java" / "guides").glob("*.md")
    return {f"habit-hooks:{s}" for s in smells | {g.stem for g in guides}}


def guard_labels() -> set[str]:
    text = (ROOT / ".github" / "workflows" / "_guards.yml").read_text(encoding="utf-8")
    found = re.findall(r'^\s+(?:ruleset|suppression)_label:\n(?:\s+.*\n)*?\s+default: "([^"]+)"', text, re.M)
    assert len(found) == 2, found
    return {f"label:{x}" for x in found}


def test_catalog_covers_every_rule_foundry_enables():
    enabled = eslint_rules() | pmd_rules() | ruff_families() | tuned_sensor_smells() | guard_labels()
    assert eslint_rules() and pmd_rules() and ruff_families()
    assert enabled - catalog_ids() == set()


def test_every_catalog_entry_is_complete():
    for r in tomllib.loads((RULES / "catalog.toml").read_text(encoding="utf-8"))["rule"]:
        assert r["why"].strip() and r["fix"].strip(), r["id"]
        assert r["suppressible"] in {"never", "with-label", "inline-with-reason"}, r["id"]
        missing = [p for p in r["see"] if not (ROOT / p).exists()]
        assert not missing, f"{r['id']} cites missing files {missing}"
        # The id lands unescaped in a JSON telemetry line, so keep it to safe characters.
        assert re.fullmatch(r"[A-Za-z0-9:_.-]+", r["id"]), r["id"]


def test_every_fixed_matcher_id_is_in_the_catalog():
    ids = catalog_ids()
    dangling = [i for m in matchers() for i in m["ids"] if "{" not in i and i not in ids]
    assert not dangling


@pytest.mark.parametrize("m", matchers(), ids=lambda m: f"{m['tool']}:{m['pattern'][:30]}")
def test_each_matcher_explains_its_own_example(m):
    assert explain.match_ids([m["example"]], explain.load_rules(RULES)), m["example"]


def run(*args, stdin="", **env):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True,
                          text=True, encoding="utf-8", env={**os.environ, **env})


def test_explains_an_id():
    r = run("eslint:max-len")
    assert r.returncode == 0, r.stderr
    assert "why:" in r.stdout and "120" in r.stdout and "suppressible: with-label" in r.stdout


def test_unknown_id_fails_and_names_close_ids():
    r = run("eslint:max-lenn")
    assert r.returncode == 1
    assert "eslint:max-len" in r.stderr


def test_match_prints_only_catalog_ids():
    log = ("src/a.ts\n  3:1  error  Unexpected console statement  no-console\n"
           "  9:1  error  This line has a length of 130. Maximum allowed is 120  max-len\n")
    r = run("--match", stdin=log)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["eslint:max-len"]


def test_match_sees_through_colour_and_crlf():
    log = "\x1b[2m  9:1\x1b[22m  \x1b[31merror\x1b[39m  Too long  \x1b[2mmax-len\x1b[22m\r\n"
    assert run("--match", stdin=log).stdout.split() == ["eslint:max-len"]


def test_match_lists_each_id_once_in_first_seen_order():
    log = ("── oversized-function (2 issues) ──\n"
           "── deep-nesting (1 issue) ──\n")
    got = run("--match", stdin=log).stdout.split()
    assert got == ["habit-hooks:oversized-function", "habit-hooks:snooze", "habit-hooks:deep-nesting"]


def telemetry(tmp_path: Path, *rows: dict) -> Path:
    p = tmp_path / "telemetry.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return p


def test_last_explains_the_most_recent_failure(tmp_path):
    p = telemetry(
        tmp_path,
        {"ms": 100, "verb": "lint", "exit": 1, "rules": ["eslint:max-len"]},
        {"ms": 200, "verb": "test", "exit": 1, "rules": ["coverage:floor"]},
        {"ms": 300, "verb": "lint", "exit": 0},
    )
    r = run("--last", str(p))
    assert r.returncode == 0, r.stderr
    assert "test" in r.stdout.splitlines()[0]
    assert "coverage:floor" in r.stdout and "eslint:max-len" not in r.stdout


def test_last_says_when_the_failure_matched_nothing(tmp_path):
    p = telemetry(tmp_path, {"ms": 1, "verb": "lint", "exit": 2, "rules": []})
    r = run("--last", str(p))
    assert r.returncode == 0
    assert "no catalog rule" in r.stdout


def test_last_tells_unrecorded_rules_apart_from_no_match(tmp_path):
    p = telemetry(tmp_path, {"ms": 1, "verb": "lint", "exit": 2})
    r = run("--last", str(p))
    assert "not recorded" in r.stdout and "no catalog rule" not in r.stdout


def test_json_output_is_the_entry(tmp_path):
    r = run("--json", "gitleaks:leak")
    entry = json.loads(r.stdout)
    assert entry["id"] == "gitleaks:leak" and entry["suppressible"] == "never"
