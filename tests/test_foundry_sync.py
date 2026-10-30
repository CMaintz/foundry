"""foundry-init.sh --sync: move a scaffolded repo to a Foundry release. The scripts pin and its
digest lines are copied from the tag's own template (never computed from downloaded bytes, so
a moved tag still fails setup:foundry-scripts), version-tag workflow refs follow, and the rest
of the template drift is shown, not applied. A fake `curl` on PATH serves templates per tag
and a local git repo stands in for the tag listing, so no network is touched.
"""
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
INIT = (ROOT / "scripts" / "foundry-init.sh").as_posix()
# Resolved through PATH: a bare "bash" on Windows hits System32's WSL launcher first.
BASH = shutil.which("bash") or "bash"
DIGEST_LINE = re.compile(r"^([\w./-]+) ([0-9a-f]{64})$", re.M)
REF_LINE = re.compile(r'^FOUNDRY_SCRIPTS_REF = "[^"]*"$', re.M)
SHA = "0123456789abcdef0123456789abcdef01234567"

FAKE_CURL = """#!/bin/sh
# Stand-in for `curl -fsSL <url> -o <file>`: serve raw.githubusercontent paths from $FAKE_SERVED.
[ -n "${FAKE_OFFLINE:-}" ] && exit 7
url="" out=""
while [ $# -gt 0 ]; do
  case "$1" in -o) out="$2"; shift 2 ;; -*) shift ;; *) url="$1"; shift ;; esac
done
src="$FAKE_SERVED/${url#https://raw.githubusercontent.com/CMaintz/foundry/}"
[ -f "$src" ] || exit 22
cat "$src" > "$out"
"""

WORKFLOWS = {
    "gate.yml": "jobs:\n  gate:\n    uses: CMaintz/foundry/.github/workflows/gate.yml@v1.0.0   # facade\n",
    "security.yml": f"jobs:\n  security:\n    uses: CMaintz/foundry/.github/workflows/security.yml@{SHA} # v1.0.0\n",
    "ratchet.yml": "jobs:\n  ratchet:\n    uses: CMaintz/foundry/.github/workflows/ratchet-report.yml@main\n",
    "bootstrap.yml": "jobs:\n  bootstrap:\n    uses: CMaintz/foundry/.github/workflows/bootstrap.yml@v1\n",
}


def digests(text: str) -> dict[str, str]:
    return dict(DIGEST_LINE.findall(text))


def release_template(stack: str, tag: str) -> str:
    """The stack's template as a release commit has it: pinned to the tag, with digests that
    match no real file (a sync that computes digests instead of copying them gets them wrong)
    and one script the consumer has not fetched yet."""
    text = (ROOT / "mise" / f"{stack}.toml").read_text(encoding="utf-8")
    text = REF_LINE.sub(f'FOUNDRY_SCRIPTS_REF = "{tag}"', text)
    text = DIGEST_LINE.sub(lambda m: f"{m[1]} {'a' * 64}", text)
    return text.replace("scripts='\n", "scripts='\nfoundry-new-script " + "b" * 64 + "\n", 1)


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=cwd, check=True, capture_output=True)


class Consumer:
    """A repo scaffolded at v1.0.0 from the stack's template, plus a fake Foundry upstream."""

    def __init__(self, tmp: Path, stack: str, tags: list[str]):
        self.stack = stack
        self.repo = tmp / "repo"
        served = tmp / "served"
        bin_dir = tmp / "bin"
        self.remote = tmp / "remote"
        for d in (self.repo / ".github" / "workflows", bin_dir, self.remote):
            d.mkdir(parents=True)
        old = REF_LINE.sub('FOUNDRY_SCRIPTS_REF = "v1.0.0"', release_template(stack, "v1.0.0"))
        old = old.replace("foundry-new-script " + "b" * 64 + "\n", "")
        # A consumer edit the sync must keep: it rewrites only the pin and digest lines.
        self.mise = old.replace("[tools]\n", "[tools]\n# consumer's own tool pin\n", 1)
        self.write("mise.toml", self.mise)
        for name, body in WORKFLOWS.items():
            self.write(f".github/workflows/{name}", body)
        for tag in tags:
            t = served / tag / "mise" / f"{stack}.toml"
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(release_template(stack, tag), encoding="utf-8", newline="\n")
        git(self.remote, "init", "-q")
        git(self.remote, "commit", "-q", "--allow-empty", "-m", "seed")
        for tag in tags:
            git(self.remote, "tag", "-a", "-m", tag, tag)
        # Not releases: the floating major alias and a prerelease must never be picked.
        git(self.remote, "tag", "v9")
        git(self.remote, "tag", "v9.0.0-rc.1")
        (bin_dir / "curl").write_text(FAKE_CURL, encoding="utf-8", newline="\n")
        (bin_dir / "curl").chmod(0o755)
        self.env = {**os.environ, "FAKE_SERVED": str(served), "FOUNDRY_REMOTE": str(self.remote),
                    "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        self.served = served

    def write(self, rel: str, text: str) -> None:
        (self.repo / rel).write_text(text, encoding="utf-8", newline="\n")

    def read(self, rel: str) -> str:
        return (self.repo / rel).read_text(encoding="utf-8")

    def snapshot(self) -> dict[str, str]:
        return {p.relative_to(self.repo).as_posix(): p.read_text(encoding="utf-8")
                for p in self.repo.rglob("*") if p.is_file()}

    def sync(self, *args: str, **env: str) -> subprocess.CompletedProcess:
        return subprocess.run([BASH, INIT, "--sync", *args], cwd=self.repo, env={**self.env, **env},
                              capture_output=True, text=True)


@pytest.fixture
def ts(tmp_path):
    return Consumer(tmp_path, "ts", ["v1.0.0", "v1.2.0", "v1.10.0"])


def test_ref_and_digests_come_from_the_tags_template(ts):
    r = ts.sync("v1.2.0")
    assert r.returncode == 0, r.stderr
    mise = ts.read("mise.toml")
    template = (ts.served / "v1.2.0" / "mise" / "ts.toml").read_text(encoding="utf-8")
    assert tomllib.loads(mise)["env"]["FOUNDRY_SCRIPTS_REF"] == "v1.2.0"
    assert digests(mise) == digests(template)
    assert "foundry-new-script" in digests(mise)
    assert "# consumer's own tool pin" in mise


def test_drift_is_shown_not_applied(ts):
    (ts.served / "v1.2.0" / "mise" / "ts.toml").write_text(
        release_template("ts", "v1.2.0") + '\n[tasks."new-verb"]\nrun = "true"\n', encoding="utf-8", newline="\n")
    r = ts.sync("v1.2.0")
    assert r.returncode == 0, r.stderr
    assert '+[tasks."new-verb"]' in r.stdout
    assert "-# consumer's own tool pin" in r.stdout
    assert "new-verb" not in ts.read("mise.toml")


def test_no_tag_means_the_latest_release(ts):
    r = ts.sync()
    assert r.returncode == 0, r.stderr
    assert tomllib.loads(ts.read("mise.toml"))["env"]["FOUNDRY_SCRIPTS_REF"] == "v1.10.0"


def test_only_version_tag_workflow_pins_move(ts):
    r = ts.sync("v1.2.0")
    assert r.returncode == 0, r.stderr
    assert "gate.yml@v1.2.0" in ts.read(".github/workflows/gate.yml")
    for name in ("security.yml", "ratchet.yml", "bootstrap.yml"):
        assert ts.read(f".github/workflows/{name}") == WORKFLOWS[name], name
        assert name in r.stdout, name


def test_second_run_changes_nothing(ts):
    assert ts.sync("v1.2.0").returncode == 0
    before = ts.snapshot()
    r = ts.sync("v1.2.0")
    assert r.returncode == 0, r.stderr
    assert ts.snapshot() == before


def test_offline_fails_closed_and_leaves_the_repo_alone(ts):
    before = ts.snapshot()
    r = ts.sync("v1.2.0", FAKE_OFFLINE="1")
    assert r.returncode != 0
    assert "v1.2.0" in r.stderr
    assert ts.snapshot() == before
    r = ts.sync(FOUNDRY_REMOTE=str(ts.remote / "missing"))
    assert r.returncode != 0
    assert "tags" in r.stderr
    assert ts.snapshot() == before


def test_kotlin_is_detected_without_a_habit_hooks_plugin(tmp_path):
    kt = Consumer(tmp_path, "kotlin", ["v1.2.0"])
    r = kt.sync("v1.2.0")
    assert r.returncode == 0, r.stderr
    assert tomllib.loads(kt.read("mise.toml"))["env"]["FOUNDRY_SCRIPTS_REF"] == "v1.2.0"
