import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ruleset_guard.py"
sys.path.insert(0, str(SCRIPT.parent))

import ruleset_guard as guard  # noqa: E402


def eslint(entries):
    """{(file, rule): count} -> eslint-suppressions.json text."""
    d = {}
    for (f, rule), n in entries.items():
        d.setdefault(f, {})[rule] = {"count": n}
    return json.dumps(d)


class TestEslint:
    def test_unchanged_is_safe(self):
        text = eslint({("a.ts", "no-any"): 2})
        assert guard.loosened("eslint", text, text) == []

    def test_decrease_and_removal_are_safe(self):
        old = eslint({("a.ts", "no-any"): 2, ("b.ts", "max-lines"): 1})
        new = eslint({("a.ts", "no-any"): 1})
        assert guard.loosened("eslint", old, new) == []

    def test_increase_is_a_loosening(self):
        old = eslint({("a.ts", "no-any"): 1})
        new = eslint({("a.ts", "no-any"): 3})
        assert guard.loosened("eslint", old, new) == [("a.ts", "no-any")]

    def test_offset_attack_is_caught(self):
        # Fixing one violation while suppressing another nets zero in aggregate.
        old = eslint({("a.ts", "no-any"): 2})
        new = eslint({("a.ts", "no-any"): 1, ("b.ts", "no-any"): 1})
        assert guard.loosened("eslint", old, new) == [("b.ts", "no-any")]

    def test_new_file_from_nothing_is_a_loosening(self):
        assert guard.loosened("eslint", "", eslint({("a.ts", "no-any"): 1})) == [("a.ts", "no-any")]

    def test_deleting_the_baseline_is_safe(self):
        assert guard.loosened("eslint", eslint({("a.ts", "no-any"): 1}), "") == []

    def test_missing_count_counts_as_zero(self):
        assert guard.eslint_counts({"a.ts": {"r": {}}})[("a.ts", "r")] == 0


class TestSnooze:
    OLD = json.dumps({"snoozed": [{"file": "a.py", "smell": "oversized-file"}]})

    def test_reorder_is_safe(self):
        old = json.dumps({"s": [{"file": "a"}, {"file": "b"}]})
        new = json.dumps({"s": [{"file": "b"}, {"file": "a"}]})
        assert guard.loosened("snooze", old, new) == []

    def test_removal_is_safe(self):
        assert guard.loosened("snooze", self.OLD, json.dumps({"snoozed": []})) == []

    def test_added_entry_is_a_loosening(self):
        new = json.dumps(
            {"snoozed": [{"file": "a.py", "smell": "oversized-file"}, {"file": "b.py", "smell": "oversized-file"}]}
        )
        assert set(guard.loosened("snooze", self.OLD, new)) == {"b.py", "oversized-file"}

    def test_value_counts_walks_nested_scalars(self):
        counts = guard.value_counts({"x": [1, {"y": 1}], "z": None})
        assert counts[1] == 2 and counts[None] == 1


class TestLines:
    def test_blank_lines_and_whitespace_are_ignored(self):
        assert guard.loosened("lines", "v1\nv2\n", "  v1\n\nv2  \n") == []

    def test_added_violation_is_a_loosening(self):
        assert guard.loosened("lines", "v1\n", "v1\nv2\n") == ["v2"]

    def test_duplicate_line_is_a_loosening(self):
        assert guard.loosened("lines", "v1\n", "v1\nv1\n") == ["v1"]


class TestCoverage:
    def test_adding_fixtures_is_safe(self):
        old = json.dumps({"fixtures": ["a"]})
        new = json.dumps({"fixtures": ["a", "b"]})
        assert guard.loosened("coverage", old, new) == []

    def test_removing_a_fixture_is_a_loosening(self):
        old = json.dumps({"fixtures": ["a", "b"]})
        new = json.dumps({"fixtures": ["a"]})
        assert guard.loosened("coverage", old, new) == ["b"]

    def test_deleting_the_manifest_is_a_loosening(self):
        assert guard.loosened("coverage", json.dumps({"fixtures": ["a"]}), "") == ["a"]


@pytest.fixture
def repo(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("config", "commit.gpgsign", "false")

    def commit(text, path="snooze.json"):
        (tmp_path / path).write_text(text)
        git("add", "-A")
        git("commit", "-qm", "c")
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True)
        return out.stdout.strip()

    return tmp_path, commit


def run_cli(cwd, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)


class TestCli:
    def test_exit_0_when_the_baseline_shrinks(self, repo):
        cwd, commit = repo
        base = commit(json.dumps({"s": ["a", "b"]}))
        head = commit(json.dumps({"s": ["a"]}))
        assert run_cli(cwd, "snooze", base, head, "snooze.json").returncode == 0

    def test_exit_1_and_reports_when_the_baseline_grows(self, repo):
        cwd, commit = repo
        base = commit(json.dumps({"s": ["a"]}))
        head = commit(json.dumps({"s": ["a", "b"]}))
        result = run_cli(cwd, "snooze", base, head, "snooze.json")
        assert result.returncode == 1
        assert "added/increased: b" in result.stderr

    def test_file_absent_at_base_is_treated_as_empty(self, repo):
        cwd, commit = repo
        base = commit("x", path="other.txt")
        head = commit("v1\n", path="store.txt")
        assert run_cli(cwd, "lines", base, head, "store.txt").returncode == 1
