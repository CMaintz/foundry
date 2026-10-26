"""The verb-wrap smell-count fold: a wrapped verb whose command writes the smells
sidecar gets a `smells` field on its telemetry line; one that writes nothing does not;
and a stale sidecar from before the run never attaches. The timing/exit behaviour is
covered implicitly (the line is only written when the verb ran). See loop-telemetry.md.
"""
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WRAP = ROOT / "scripts" / "foundry-verb-wrap"
# A bare "bash" on Windows hits System32's WSL launcher first; resolve through PATH,
# matching the sibling shell tests (test_release_pin.py). bash is always present on CI
# (Linux) and the local Git Bash shell, so there is nothing to skip for.
BASH = shutil.which("bash") or "bash"


def run_verb(tmp_path, inner_cmd):
    """Run `foundry-verb-wrap lint -- sh -c <inner_cmd>` with telemetry + sidecar under
    tmp_path, and return the parsed telemetry lines."""
    telemetry = tmp_path / "telemetry.jsonl"
    env = {
        "PATH": __import__("os").environ["PATH"],
        "FOUNDRY_TELEMETRY": str(telemetry),
        "FOUNDRY_SMELLS": str(tmp_path / "smells.json"),
    }
    subprocess.run([BASH, str(WRAP), "lint", "--", "sh", "-c", inner_cmd], env=env, check=False)
    return [json.loads(ln) for ln in telemetry.read_text().splitlines() if ln.strip()]


def test_fold_in_when_command_writes_sidecar(tmp_path):
    rows = run_verb(tmp_path, 'printf \'{"oversized-file":2}\\n\' > "$FOUNDRY_SMELLS"')
    assert len(rows) == 1
    assert rows[0]["verb"] == "lint"
    assert rows[0]["smells"] == {"oversized-file": 2}


def test_no_smells_key_when_command_writes_nothing(tmp_path):
    rows = run_verb(tmp_path, "true")
    assert len(rows) == 1
    assert "smells" not in rows[0]  # distinct from an empty {}


def test_stale_sidecar_is_not_attached(tmp_path):
    # A sidecar left by an earlier run must be cleared before the command, so a verb
    # that produces none never inherits the previous verb's counts.
    (tmp_path / "smells.json").write_text('{"stale":9}\n')
    rows = run_verb(tmp_path, "true")
    assert "smells" not in rows[0]


def test_non_object_sidecar_is_ignored(tmp_path):
    rows = run_verb(tmp_path, 'printf \'not json\\n\' > "$FOUNDRY_SMELLS"')
    assert "smells" not in rows[0]


def test_exit_code_is_propagated(tmp_path):
    env = {
        "PATH": __import__("os").environ["PATH"],
        "FOUNDRY_TELEMETRY": str(tmp_path / "t.jsonl"),
        "FOUNDRY_SMELLS": str(tmp_path / "s.json"),
    }
    r = subprocess.run([BASH, str(WRAP), "lint", "--", "sh", "-c", "exit 3"], env=env, check=False)
    assert r.returncode == 3
