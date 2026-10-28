"""Tests for the changed-scope checks in the stack templates, run from a monorepo package.

A package-level mise.toml runs its tasks from the package dir, so the file lists these
checks build must be relative to it. Each test pulls the task's script out of
mise/<stack>.toml, runs it with bash in a throwaway repo, and stubs the linters with
scripts that record the paths they were handed.
"""

import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

MISE = Path(__file__).resolve().parent.parent / "mise"


def task_script(stack, task):
    run = tomllib.loads((MISE / f"{stack}.toml").read_text(encoding="utf-8"))["tasks"][task]["run"]
    return run[0] if isinstance(run, list) else run


def git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write(repo, files):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def monorepo(tmp_path, base, change):
    """A repo whose last commit applies `change` on top of `base`; returns (repo, base sha)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo, base)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    sha = git(repo, "rev-parse", "HEAD")
    write(repo, change)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "change")
    return repo, sha


def run_stubbed(tmp_path, script, cwd, tools, env):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in tools:
        stub = bin_dir / tool
        stub.write_text(f'#!/bin/sh\nprintf \'%s\\n\' "$@" >> "{(tmp_path / tool).as_posix()}"\n', encoding="utf-8")
        stub.chmod(0o755)
    env = {**os.environ, **env, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    r = subprocess.run([shutil.which("bash"), "-c", script], cwd=cwd, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return {t: (tmp_path / t).read_text(encoding="utf-8").splitlines() if (tmp_path / t).exists() else [] for t in tools}


@pytest.mark.parametrize("stack", ["ts", "js"])
def test_node_lint_hands_package_relative_paths_to_eslint_and_prettier(tmp_path, stack):
    repo, base = monorepo(
        tmp_path,
        {"pkg/src/a.ts": "a\n", "other/src/b.ts": "b\n"},
        {"pkg/src/a.ts": "a2\n", "pkg/src/my file.ts": "c\n", "pkg/README.md": "r\n", "other/src/b.ts": "b2\n"},
    )
    write(repo, {"pkg/src/new.ts": "n\n"})
    calls = run_stubbed(
        tmp_path, task_script(stack, "lint"), repo / "pkg", ["eslint", "prettier"], {"FOUNDRY_SINCE": base}
    )
    assert calls["eslint"] == ["src/a.ts", "src/my file.ts", "src/new.ts"]
    assert calls["prettier"] == ["--check", "--ignore-unknown", "README.md", "src/a.ts", "src/my file.ts", "src/new.ts"]


def test_java_novar_checks_changed_main_java_in_a_package(tmp_path):
    repo, base = monorepo(
        tmp_path,
        {"svc/src/main/java/A.java": "class A {}\n"},
        {"svc/src/main/java/A.java": "class A { void f() {} }\n", "svc/src/test/java/T.java": "class T {}\n"},
    )
    calls = run_stubbed(tmp_path, task_script("java", "novar"), repo / "svc", ["pmd"], {"FOUNDRY_BASE_REF": base})
    assert "-d=src/main/java/A.java" in calls["pmd"]
    assert not any("test/java" in a for a in calls["pmd"])
