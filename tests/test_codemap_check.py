"""Tests for scripts/codemap-check: citation resolution against git, and staleness.

Each test builds a throwaway git repo in tmp_path and runs the script as a subprocess from
its root, so the exit code and printed lines are what a consumer's `codemap:check` sees.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "codemap-check"


def git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def commit(repo, files, msg="c"):
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


def write_map(repo, sha, body, name="orders.md"):
    p = repo / "docs" / "codemap" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\nsha: {sha}\nslice: orders\nkind: domain\n---\n\n{body}\n", encoding="utf-8")


def run(repo, *args):
    r = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=repo, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def repo_with_orders(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    sha = commit(
        repo,
        {
            "src/orders.py": "class OrderService:\n    def create(self):\n        pass\n",
            "src/lines.py": "class OrderLine:\n    pass\n",
        },
    )
    return repo, sha


def test_valid_map_passes(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    write_map(repo, sha, "Orders are made by `src/orders.py#OrderService.create` under `src/`; `C#` is not a path.")
    code, out = run(repo)
    assert code == 0, out
    assert "staleness unknown" not in out


def test_renamed_file_fails_for_symbol_and_bare_citations(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    write_map(repo, sha, "Made by `src/orders.py#OrderService`.\n\nSee `src/lines.py`.")
    git(repo, "mv", "src/orders.py", "src/order_service.py")
    git(repo, "mv", "src/lines.py", "src/order_lines.py")
    git(repo, "commit", "-q", "-m", "rename")
    code, out = run(repo)
    assert code == 1
    assert "docs/codemap/orders.md:7 src/orders.py#OrderService" in out
    assert "docs/codemap/orders.md:9 src/lines.py" in out


def test_removed_symbol_fails(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    write_map(repo, sha, "Made by `src/orders.py#OrderService.create`.")
    commit(repo, {"src/orders.py": "class OrderService:\n    def place(self):\n        pass\n"})
    code, out = run(repo)
    assert code == 1
    assert "src/orders.py#OrderService.create" in out
    assert "create" in out.split("src/orders.py#OrderService.create", 1)[1]


def test_symbol_only_inside_longer_identifier_fails(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    write_map(repo, sha, "Lines are `src/lines.py#Order`.")
    code, out = run(repo)
    assert code == 1
    assert "docs/codemap/orders.md:7 src/lines.py#Order" in out


def test_missing_codemap_dir_exits_zero_with_notice(tmp_path):
    repo, _ = repo_with_orders(tmp_path)
    code, out = run(repo)
    assert code == 0
    assert len(out.strip().splitlines()) == 1


def test_staleness_counts_only_commits_touching_cited_files(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    write_map(repo, sha, "Made by `src/orders.py#OrderService`.")
    commit(repo, {"src/orders.py": "class OrderService:\n    x = 1\n"})
    commit(repo, {"README.md": "unrelated\n"})
    code, out = run(repo)
    assert code == 0, out
    assert "docs/codemap/orders.md: 1 commit" in out


def test_unknown_sha_is_reported_not_failed(tmp_path):
    repo, _ = repo_with_orders(tmp_path)
    write_map(repo, "0" * 40, "Made by `src/orders.py#OrderService`.")
    write_map(repo, "", "Made by `src/orders.py#OrderService`.", name="other.md")
    code, out = run(repo)
    assert code == 0, out
    assert "docs/codemap/orders.md: staleness unknown" in out
    assert "docs/codemap/other.md: staleness unknown" in out


def test_map_dir_is_overridable(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    p = repo / "maps" / "orders.md"
    p.parent.mkdir()
    p.write_text(f"---\nsha: {sha}\n---\n\n`src/orders.py#Gone`\n")
    code, out = run(repo, "maps")
    assert code == 1
    assert "maps/orders.md:5 src/orders.py#Gone" in out


def test_code_fences_and_double_backtick_quotes_are_not_citations(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    write_map(repo, sha, "Quoted: `` `src/gone.py#X` ``.\n\n```\n`src/gone.py#Y`\n```")
    code, out = run(repo)
    assert code == 0, out


def test_non_ascii_paths_resolve(tmp_path):
    repo, _ = repo_with_orders(tmp_path)
    sha = commit(repo, {"src/caf\u00e9.py": "class Menu:\n    pass\n", "src/\u00c1.txt": "x\n"})
    write_map(repo, sha, "Menus are `src/caf\u00e9.py#Menu`.")
    code, out = run(repo)
    assert code == 0, out


def test_bom_before_frontmatter_still_reads_sha(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    p = repo / "docs" / "codemap" / "orders.md"
    p.parent.mkdir(parents=True)
    p.write_bytes(f"\ufeff---\nsha: {sha}\n---\n\n`src/orders.py#OrderService`\n".encode())
    code, out = run(repo)
    assert code == 0, out
    assert "staleness unknown" not in out


def test_cited_file_deleted_from_working_tree_says_so(tmp_path):
    repo, sha = repo_with_orders(tmp_path)
    write_map(repo, sha, "Lines are `src/lines.py#OrderLine`.")
    (repo / "src" / "lines.py").unlink()
    code, out = run(repo)
    assert code == 1
    assert "src/lines.py#OrderLine file missing from working tree" in out


def test_missing_explicit_map_dir_is_an_error(tmp_path):
    repo, _ = repo_with_orders(tmp_path)
    code, _ = run(repo, "doc/codemap")
    assert code == 2
