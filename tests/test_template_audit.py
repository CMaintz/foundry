"""Tests for the secret scan every stack template's `audit` verb runs.

The scan block is pulled out of mise/<stack>.toml and run with bash in a throwaway git
repo, so what is asserted is what a consumer's `mise run audit` does. gitleaks comes from
foundry's own [tools] pin.
"""

import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

TEMPLATES = sorted((Path(__file__).resolve().parent.parent / "mise").glob("*.toml"))
# Built at runtime so foundry's own history scan never sees a literal key.
LEAK = 'aws_key = "' + "AKIA" + "QWERTYUIOPASDFGH" + '"\n'


def audit_steps(template):
    run = tomllib.loads(template.read_text(encoding="utf-8"))["tasks"]["audit"]["run"]
    return run if isinstance(run, list) else [run]


def scan_block():
    blocks = {t.name: [s for s in audit_steps(t) if "gitleaks dir" in s] for t in TEMPLATES}
    assert all(len(b) == 1 for b in blocks.values()), blocks
    distinct = {b[0] for b in blocks.values()}
    assert len(distinct) == 1, "the templates' secret scans have drifted apart"
    return distinct.pop()


def git(repo, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def write(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def scan(cwd):
    r = subprocess.run([shutil.which("bash"), "-c", scan_block()], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo, ".gitignore", ".venv/\n")
    write(repo, "src/app.txt", "clean\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "c")
    return repo


def test_every_template_pins_gitleaks_and_runs_the_scan():
    scan_block()
    for t in TEMPLATES:
        assert "gitleaks" in tomllib.loads(t.read_text(encoding="utf-8"))["tools"], t.name


def test_ignored_dependency_tree_is_not_scanned(repo):
    write(repo, ".venv/lib/site-packages/fixture.txt", LEAK)
    code, out = scan(repo)
    assert code == 0, out


def test_untracked_file_is_scanned_and_real_index_untouched(repo):
    write(repo, "src/new.txt", LEAK)
    code, out = scan(repo)
    assert code == 1, out
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True)
    assert status.stdout.strip() == "?? src/new.txt"


def test_package_dir_honours_root_gitleaks_toml(repo):
    write(repo, "pkg/src/fixture.txt", LEAK)
    assert scan(repo / "pkg")[0] == 1
    write(repo, ".gitleaks.toml", "[extend]\nuseDefault = true\n[allowlist]\npaths = ['''^src/fixture\\.txt$''']\n")
    code, out = scan(repo / "pkg")
    assert code == 0, out
