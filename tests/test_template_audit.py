"""Tests for the secret scan every stack template's `audit` verb runs.

The scan block is pulled out of mise/<stack>.toml and run with sh in a throwaway git
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
    blocks = {t.name: [s for s in audit_steps(t) if "gitleaks git" in s] for t in TEMPLATES}
    assert all(len(b) == 1 for b in blocks.values()), blocks
    distinct = {b[0] for b in blocks.values()}
    assert len(distinct) == 1, "the templates' secret scans have drifted apart"
    return distinct.pop()


def git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def write(repo, rel, text):
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def commit(repo, msg="c"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


def push(repo):
    """Stand in for a push: the default branch's remote-tracking ref now holds HEAD."""
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")


def scan(cwd):
    # sh, not bash: Linux CI runs it under dash, so a bashism fails here first.
    r = subprocess.run([shutil.which("sh"), "-c", scan_block()], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


@pytest.fixture
def repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo, ".gitignore", ".venv/\n")
    write(repo, "src/app.txt", "clean\n")
    commit(repo)
    push(repo)
    return repo


def test_every_template_pins_gitleaks_and_runs_the_scan():
    scan_block()
    for t in TEMPLATES:
        assert "gitleaks" in tomllib.loads(t.read_text(encoding="utf-8"))["tools"], t.name


def test_ignored_dependency_tree_is_not_scanned(repo):
    write(repo, ".venv/lib/site-packages/fixture.txt", LEAK)
    code, out = scan(repo)
    assert code == 0, out


def test_history_already_on_the_default_branch_is_not_rescanned(repo):
    write(repo, "src/old.txt", LEAK)
    commit(repo)
    push(repo)
    code, out = scan(repo)
    assert code == 0, out


def test_unpushed_commit_is_scanned(repo):
    write(repo, "src/new.txt", LEAK)
    commit(repo)
    git(repo, "rm", "-q", "src/new.txt")
    commit(repo)
    code, out = scan(repo)
    assert code != 0, out


def test_without_a_default_branch_every_commit_is_scanned(repo):
    git(repo, "update-ref", "-d", "refs/remotes/origin/main")
    write(repo, "src/new.txt", LEAK)
    commit(repo)
    git(repo, "rm", "-q", "src/new.txt")
    commit(repo)
    code, out = scan(repo)
    assert code != 0, out


def test_unstaged_edit_is_scanned(repo):
    write(repo, "src/app.txt", LEAK)
    code, out = scan(repo)
    assert code != 0, out


def test_staged_edit_is_scanned(repo):
    write(repo, "src/app.txt", LEAK)
    git(repo, "add", "src/app.txt")
    code, out = scan(repo)
    assert code != 0, out


def test_untracked_file_is_scanned_without_touching_git(repo):
    write(repo, "src/my new.txt", LEAK)
    objects = git(repo, "count-objects")
    code, out = scan(repo)
    assert code != 0, out
    assert "leaks found" in out, out
    assert git(repo, "status", "--porcelain") == '?? "src/my new.txt"\n'
    assert git(repo, "count-objects") == objects


def test_package_dir_scans_the_repo_and_honours_root_gitleaks_toml(repo):
    write(repo, "pkg/src/fixture.txt", LEAK)
    write(repo, "other/leak.txt", LEAK)
    assert scan(repo / "pkg")[0] != 0
    allow = "[extend]\nuseDefault = true\n[allowlist]\npaths = ['''^(pkg/src/fixture|other/leak)\\.txt$''']\n"
    write(repo, ".gitleaks.toml", allow)
    code, out = scan(repo / "pkg")
    assert code == 0, out
