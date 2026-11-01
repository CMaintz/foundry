"""Tests for the js template's own `typecheck` and `test` verbs.

Each test pulls the task's script out of mise/js.toml and runs it with bash and the real
node from PATH in a throwaway git repo, so what is asserted is what a consumer's
`mise run typecheck` / `mise run test` does.
"""

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

MISE = Path(__file__).resolve().parent.parent / "mise" / "js.toml"
COVERED = "export const double = (n) => n * 2;\n"
TEST = (
    'import assert from "node:assert/strict";\n'
    'import test from "node:test";\n'
    'import { double } from "../src/lib.mjs";\n'
    'test("doubles", () => assert.equal(double(2), 4));\n'
)


def run_task(repo, task, files):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    script = tomllib.loads(MISE.read_text(encoding="utf-8"))["tasks"][task]["run"]
    env = {**os.environ, "FOUNDRY_COVERAGE_LINES": "80"}
    return subprocess.run([shutil.which("bash"), "-c", script], cwd=repo, env=env, capture_output=True, text=True)


def repo_at(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_typecheck_fails_on_a_new_file_node_cannot_parse(tmp_path):
    r = run_task(repo_at(tmp_path), "typecheck", {"src/ok.mjs": COVERED, "src/broken.mjs": "export const = 1;\n"})
    assert r.returncode != 0
    assert "broken.mjs" in r.stderr


def test_typecheck_passes_valid_javascript(tmp_path):
    r = run_task(repo_at(tmp_path), "typecheck", {"src/ok.mjs": COVERED, "src/cjs.cjs": "module.exports = 1;\n"})
    assert r.returncode == 0, r.stdout + r.stderr


def test_test_fails_when_no_tests_are_found(tmp_path):
    r = run_task(repo_at(tmp_path), "test", {"src/lib.mjs": COVERED})
    assert r.returncode != 0
    assert "no tests found" in r.stderr


def test_test_passes_a_covered_suite(tmp_path):
    r = run_task(repo_at(tmp_path), "test", {"src/lib.mjs": COVERED, "test/lib.test.mjs": TEST})
    assert r.returncode == 0, r.stdout + r.stderr


def test_test_fails_below_the_coverage_floor(tmp_path):
    lib = COVERED + "export function unused(n) {\n  const a = n + 1;\n  const b = a * 2;\n  return b - 3;\n}\n"
    r = run_task(repo_at(tmp_path), "test", {"src/lib.mjs": lib, "test/lib.test.mjs": TEST})
    assert r.returncode != 0
    assert "coverage does not meet threshold" in r.stdout + r.stderr
