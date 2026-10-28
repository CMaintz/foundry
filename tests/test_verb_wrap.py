"""scripts/foundry-verb-wrap: the command's exit code and output pass through unchanged
while the wrapper tees them, and a failing verb whose output matches the rule catalog gets
one `why: foundry-explain <id>` footer line per id, recorded in the telemetry line.

A broken wrapper fails green silently (every verb in every consumer's gate runs through
it), so the exit-code tests are the ones that matter most.
"""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRAP = ROOT / "scripts" / "foundry-verb-wrap"
# Resolved through PATH: a bare name on Windows can hit System32's WSL launcher first.
SH = shutil.which("sh") or "sh"
MAX_LEN = "  9:1  error  This line has a length of 130. Maximum allowed is 120  max-len"


def wrap(tmp_path: Path, script: str, wrapper: Path = WRAP, **extra) -> subprocess.CompletedProcess:
    env = {**os.environ, "FOUNDRY_TELEMETRY": str(tmp_path / "t.jsonl"), "FOUNDRY_PLACEMENT": "manual", **extra}
    return subprocess.run([SH, str(wrapper), "lint", "--", SH, "-c", script],
                          capture_output=True, env=env, cwd=tmp_path)


def row(tmp_path: Path) -> dict:
    lines = (tmp_path / "t.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1, lines
    return json.loads(lines[0])


def test_failing_exit_code_survives_the_tee(tmp_path):
    r = wrap(tmp_path, "echo out; echo err >&2; exit 3")
    assert r.returncode == 3
    assert row(tmp_path)["exit"] == 3


def test_command_not_found_keeps_its_exit_code(tmp_path):
    r = wrap(tmp_path, "no-such-command-anywhere")
    assert r.returncode == 127


def test_passing_output_is_unchanged_per_stream(tmp_path):
    r = wrap(tmp_path, f"printf 'a\\nb'; printf 'warn\\n' >&2; echo '{MAX_LEN}'")
    assert r.returncode == 0
    assert r.stdout == f"a\nb{MAX_LEN}\n".encode()
    assert r.stderr == b"warn\n"
    assert "rules" not in row(tmp_path)


def test_failure_matching_the_catalog_gets_a_footer(tmp_path):
    r = wrap(tmp_path, f"echo '{MAX_LEN}'; exit 1")
    assert r.returncode == 1
    assert r.stdout == f"{MAX_LEN}\n".encode()
    assert b"why: foundry-explain eslint:max-len" in r.stderr
    assert row(tmp_path)["rules"] == ["eslint:max-len"]


def test_rule_printed_on_stderr_is_matched_too(tmp_path):
    r = wrap(tmp_path, "echo 'ERROR: Coverage for lines (70%) does not meet global threshold (80%)' >&2; exit 1")
    assert b"why: foundry-explain coverage:floor" in r.stderr


def test_failure_with_no_catalog_rule_prints_nothing_extra(tmp_path):
    r = wrap(tmp_path, "echo '  3:1  error  Unexpected console statement  no-console'; exit 1")
    assert r.returncode == 1
    assert b"why:" not in r.stderr
    assert row(tmp_path)["rules"] == []


def test_wrapper_without_explain_beside_it_still_propagates(tmp_path):
    # A consumer whose setup:foundry-scripts predates foundry-explain caches only the wrapper.
    lone = tmp_path / "bin" / "foundry-verb-wrap"
    lone.parent.mkdir()
    shutil.copy(WRAP, lone)
    r = wrap(tmp_path, f"echo '{MAX_LEN}'; exit 4", wrapper=lone)
    assert r.returncode == 4
    assert r.stdout == f"{MAX_LEN}\n".encode()
    assert b"why:" not in r.stderr


def test_opt_out_runs_the_command_untouched(tmp_path):
    r = wrap(tmp_path, f"echo '{MAX_LEN}'; exit 1", FOUNDRY_EXPLAIN="0")
    assert r.returncode == 1
    assert b"why:" not in r.stderr
    assert "rules" not in row(tmp_path)


def test_a_child_left_holding_the_output_does_not_hang_the_verb(tmp_path):
    # A build server or daemon the command started keeps the pipes open after it exits.
    began = time.monotonic()
    r = wrap(tmp_path, "sleep 30 & echo done; exit 2")
    assert r.returncode == 2
    assert r.stdout.startswith(b"done")
    assert time.monotonic() - began < 20
