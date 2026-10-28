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

    def test_comment_lines_are_ignored(self):
        # ArchUnit's stored.rules is a Properties file with a changing '#<timestamp>'
        # comment; a prune must not look like an added line because of it.
        old = "#Tue Jan 01 00:00:00 UTC 2026\nv1\nv2\n"
        new = "#Wed Jan 02 09:30:00 UTC 2026\nv1\n"
        assert guard.loosened("lines", old, new) == []


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
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
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

    def test_unknown_kind_exits_nonzero_with_guidance(self, repo):
        cwd, _ = repo
        r = run_cli(cwd, "bogus", "a", "b", "c")
        assert r.returncode != 0
        assert "unknown kind" in (r.stdout + r.stderr)


# Directive literals assembled from fragments so this test file never contains one
# verbatim (defence-in-depth on top of the scan's path exclusion).
DISABLE = "// es" + "lint-disable-next-line no-explicit-any\n"
NOQA = "x = 1  # no" + "qa\n"
SKIP = "it" + ".skip('later', () => {})\n"


class TestInline:
    def test_added_suppression_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit("export const a = 1\n", path="a.ts")
        head = commit("export const a = 1\n" + DISABLE, path="a.ts")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1
        assert "eslint-disable" in r.stderr and "a.ts" in r.stderr

    def test_added_eslint_inline_rule_config_is_a_loosening(self, repo):
        # `/* eslint rule: "off" */` turns a rule off for the file without the word
        # "disable", so the eslint-disable count never sees it.
        cwd, commit = repo
        base = commit("export const a = 1\n", path="a.ts")
        head = commit('/* es' + 'lint no-console: "off" */\nexport const a = 1\n', path="a.ts")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "eslint-inline-config" in r.stderr

    def test_eslint_env_and_disable_comments_are_not_inline_config(self, repo):
        # A pattern loose enough to match `eslint-env` or `eslint-disable` would double
        # count every disable and flag harmless env comments.
        cwd, commit = repo
        base = commit("export const a = 1\n", path="a.ts")
        head = commit("/* es" + "lint-env node */\n/* es" + "lint-disable */\nexport const a = 1\n", path="a.ts")
        r = run_cli(cwd, "inline", base, head)
        assert "eslint-inline-config" not in r.stderr

    def test_removing_a_suppression_is_safe(self, repo):
        cwd, commit = repo
        base = commit("export const a = 1\n" + DISABLE, path="a.ts")
        head = commit("export const a = 1\n", path="a.ts")
        assert run_cli(cwd, "inline", base, head).returncode == 0

    def test_moving_within_a_file_is_safe(self, repo):
        cwd, commit = repo
        base = commit(DISABLE + "export const a = 1\n", path="a.ts")
        head = commit("export const a = 1\n" + DISABLE, path="a.ts")
        assert run_cli(cwd, "inline", base, head).returncode == 0

    def test_offset_across_files_is_caught(self, repo):
        cwd, commit = repo
        # Remove the suppression in a.ts, add one in b.ts: nets zero on a count, caught per-file.
        commit("export const a = 1\n" + DISABLE, path="a.ts")
        base = commit("export const b = 1\n", path="b.ts")
        commit("export const a = 1\n", path="a.ts")
        head = commit("export const b = 1\n" + DISABLE, path="b.ts")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "b.ts" in r.stderr

    def test_skipped_test_is_caught(self, repo):
        cwd, commit = repo
        base = commit("it('a', () => {})\n", path="a.test.ts")
        head = commit("it('a', () => {})\n" + SKIP, path="a.test.ts")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "js-skip" in r.stderr

    def test_skip_directives_only_apply_to_test_files(self, repo):
        cwd, commit = repo
        # A paging `.skip(` in app code, and `process.exit(` (which contains "xit("), must
        # NOT trip the test-skip directives - they are scoped to test files.
        base = commit("export const a = 1\n", path="app.ts")
        head = commit("const page = q.skip(10)\nprocess.exit(0)\n", path="app.ts")
        assert run_cli(cwd, "inline", base, head).returncode == 0

    def test_xit_in_a_test_file_is_caught(self, repo):
        cwd, commit = repo
        base = commit("it('a', () => {})\n", path="a.test.ts")
        head = commit("it('a', () => {})\nxit('b', () => {})\n", path="a.test.ts")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "js-xit" in r.stderr

    def test_skip_in_a_nested_pytest_file_is_caught(self, repo):
        # The default pytest layout keeps test_*.py under tests/, not at the root.
        cwd, commit = repo
        base = commit("def test_a():\n    pass\n", path="tests/test_x.py")
        head = commit("@pytest.mark." + "skip\ndef test_a():\n    pass\n", path="tests/test_x.py")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "tests/test_x.py" in r.stderr

    def test_skip_rules_ignore_a_non_test_file_under_a_test_named_dir(self, repo):
        # A glob whose `*` crossed `/` would treat test_helpers/util.py as a test file.
        cwd, commit = repo
        base = commit("x = 1\n", path="test_helpers/util.py")
        head = commit("@unittest." + "skip\nx = 1\n", path="test_helpers/util.py")
        assert run_cli(cwd, "inline", base, head).returncode == 0

    def test_noqa_in_python_is_caught(self, repo):
        cwd, commit = repo
        base = commit("x = 1\n", path="m.py")
        head = commit(NOQA, path="m.py")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "noqa" in r.stderr

    def test_non_code_file_is_ignored(self, repo):
        cwd, commit = repo
        base = commit("hello\n", path="README.md")
        head = commit("hello\n" + DISABLE, path="README.md")
        assert run_cli(cwd, "inline", base, head).returncode == 0


# (path, added line, directive) per marker family: one row per table entry, so a dropped
# or mistyped entry goes red here. Literals are fragment-built like the ones above.
ADDED_MARKERS = [
    ("a.ts", "// @ts-" + "nocheck", "ts-nocheck"),
    ("a_test.py", "@pytest.mark." + "xfail", "py-xfail"),
    ("a_test.py", "pytestmark = pytest.mark." + "skip", "py-pytestmark-skip"),
    ("FooTest.java", '@Suppress' + 'FBWarnings("EI_EXPOSE_REP")', "java-suppressfbwarnings"),
    ("Foo.java", "int x = 1; // NO" + "PMD", "java-nopmd"),
    ("Foo.kt", '@file:Suppress' + '("UNUSED")', "kotlin-file-suppress"),
    ("Foo.php", "// phpcs:" + "disable", "phpcs-ignore"),
    ("Foo.php", "/** @codeCoverage" + "Ignore */", "php-coverage-ignore"),
    ("FooTest.php", "$this->markTest" + "Skipped('later');", "phpunit-skip"),
    ("FooTests.cs", "[" + 'Ignore("later")]', "dotnet-ignore"),
    ("Foo.java", "var x = 1; // foundry-allow-" + "var: legacy", "foundry-allow"),
    ("Foo.java", "// foundry-allow-" + "smell: generated", "foundry-allow"),
]


class TestInlineMarkers:
    @pytest.mark.parametrize(("path", "line", "name"), ADDED_MARKERS)
    def test_added_marker_is_a_loosening(self, repo, path, line, name):
        cwd, commit = repo
        base = commit("x\n", path=path)
        head = commit("x\n" + line + "\n", path=path)
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and name in r.stderr and path in r.stderr


class TestInlineConfig:
    def test_editorconfig_demotion_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit("[*.cs]\n", path=".editorconfig")
        head = commit("[*.cs]\ndotnet_diagnostic.S3776.severity = none\n", path=".editorconfig")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "editorconfig-demote" in r.stderr

    def test_editorconfig_promotion_is_safe(self, repo):
        cwd, commit = repo
        base = commit("[*.cs]\n", path=".editorconfig")
        head = commit("[*.cs]\ndotnet_diagnostic.S3776.severity = warning\n", path=".editorconfig")
        assert run_cli(cwd, "inline", base, head).returncode == 0

    def test_tsconfig_unstrict_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit('{ "compilerOptions": { "strict": true } }\n', path="tsconfig.json")
        head = commit('{ "compilerOptions": { "strict": false } }\n', path="tsconfig.json")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "tsconfig-unstrict" in r.stderr

    def test_nested_tsconfig_unstrict_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit('{ "compilerOptions": { "strict": true } }\n', path="packages/a/tsconfig.json")
        head = commit('{ "compilerOptions": { "strict": false } }\n', path="packages/a/tsconfig.json")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "packages/a/tsconfig.json" in r.stderr

    def test_csproj_nowarn_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit("<Project></Project>\n", path="app.csproj")
        head = commit("<Project><PropertyGroup><NoWarn>CS1591</NoWarn></PropertyGroup></Project>\n", path="app.csproj")
        r = run_cli(cwd, "inline", base, head)
        assert r.returncode == 1 and "csproj-nowarn" in r.stderr


THREE = "it('a', () => {})\ntest('b', () => {})\nit('c', () => {})\n"


class TestTestDeletion:
    def test_deleting_a_test_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit(THREE, path="a.test.ts")
        head = commit("it('a', () => {})\nit('c', () => {})\n", path="a.test.ts")
        r = run_cli(cwd, "tests", base, head)
        assert r.returncode == 1 and "a.test.ts" in r.stderr

    def test_deleting_a_whole_test_file_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit(THREE, path="a.test.ts")
        subprocess.run(["git", "rm", "-q", "a.test.ts"], cwd=cwd, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "rm"], cwd=cwd, check=True, capture_output=True)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()
        r = run_cli(cwd, "tests", base, head)
        assert r.returncode == 1 and "a.test.ts" in r.stderr

    def test_adding_tests_is_safe(self, repo):
        cwd, commit = repo
        base = commit(THREE, path="a.test.ts")
        head = commit(THREE + "it('d', () => {})\n", path="a.test.ts")
        assert run_cli(cwd, "tests", base, head).returncode == 0

    def test_a_new_test_file_is_safe(self, repo):
        cwd, commit = repo
        base = commit(THREE, path="a.test.ts")
        head = commit("def test_x():\n    pass\n", path="b_test.py")
        assert run_cli(cwd, "tests", base, head).returncode == 0

    def test_deleting_a_test_in_a_nested_pytest_file_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit("def test_a():\n    pass\ndef test_b():\n    pass\n", path="tests/test_x.py")
        head = commit("def test_a():\n    pass\n", path="tests/test_x.py")
        r = run_cli(cwd, "tests", base, head)
        assert r.returncode == 1 and "tests/test_x.py" in r.stderr

    def test_non_test_file_is_not_counted(self, repo):
        cwd, commit = repo
        # `test(` in production code is not a test definition; removing it must not flag.
        base = commit("const r = test('x')\n", path="app.ts")
        head = commit("const r = 1\n", path="app.ts")
        assert run_cli(cwd, "tests", base, head).returncode == 0

    def test_it_each_is_counted(self, repo):
        cwd, commit = repo
        # If it.each weren't counted, base==head==1 and this would pass as safe.
        base = commit("it.each([1, 2])('n %s', (x) => {})\nit('b', () => {})\n", path="a.test.ts")
        head = commit("it('b', () => {})\n", path="a.test.ts")
        r = run_cli(cwd, "tests", base, head)
        assert r.returncode == 1 and "a.test.ts" in r.stderr

    def test_test_config_annotation_is_not_counted(self, repo):
        cwd, commit = repo
        base = commit("@TestConfiguration\nclass FooTest {}\n", path="FooTest.java")
        head = commit("class FooTest {}\n", path="FooTest.java")
        assert run_cli(cwd, "tests", base, head).returncode == 0


def labeled(name, at):
    return {"event": "labeled", "name": name, "created_at": at}


PUSHED = "2026-10-26T12:00:00Z"


class TestSignoff:
    def test_label_applied_after_the_push_signs_off(self):
        events = [labeled("suppression", "2026-10-26T12:05:00Z")]
        assert guard.signoff(events, ["suppression"], PUSHED) == (["suppression"], [])

    def test_push_after_the_label_voids_it(self):
        events = [labeled("suppression", "2026-10-26T11:55:00Z")]
        assert guard.signoff(events, ["suppression"], PUSHED) == ([], ["suppression"])

    def test_only_the_most_recent_labeled_event_counts(self):
        # Applied, removed, re-applied after review of the new push: valid.
        events = [
            labeled("suppression", "2026-10-26T11:00:00Z"),
            {"event": "unlabeled", "name": "suppression", "created_at": "2026-10-26T11:30:00Z"},
            labeled("suppression", "2026-10-26T12:10:00Z"),
        ]
        assert guard.signoff(events, ["suppression"], PUSHED) == (["suppression"], [])

    def test_another_labels_event_does_not_refresh_it(self):
        events = [labeled("ruleset-change", "2026-10-26T11:00:00Z"), labeled("agent:ready", "2026-10-26T12:30:00Z")]
        assert guard.signoff(events, ["ruleset-change"], PUSHED) == ([], ["ruleset-change"])

    def test_label_with_no_labeled_event_is_not_a_signoff(self):
        assert guard.signoff([], ["suppression"], PUSHED) == ([], ["suppression"])

    def test_offset_timestamps_compare_as_instants(self):
        events = [labeled("suppression", "2026-10-26T13:01:00+01:00")]  # 12:01Z
        assert guard.signoff(events, ["suppression"], PUSHED) == (["suppression"], [])


class TestSignoffCli:
    def test_exit_0_and_prints_valid_labels(self, tmp_path):
        ev = tmp_path / "events.jsonl"
        ev.write_text(json.dumps(labeled("suppression", "2026-10-26T12:05:00Z")) + "\n")
        r = run_cli(tmp_path, "signoff", str(ev), "suppression,ruleset-change", PUSHED)
        assert r.returncode == 0 and r.stdout.split() == ["suppression"]

    def test_exit_1_and_names_the_stale_label(self, tmp_path):
        ev = tmp_path / "events.jsonl"
        ev.write_text(json.dumps(labeled("suppression", "2026-10-26T11:05:00Z")) + "\n")
        r = run_cli(tmp_path, "signoff", str(ev), "suppression", PUSHED)
        assert r.returncode == 1 and "suppression" in r.stderr and r.stdout == ""


def commit_tree(cwd, files=None, remove=()):
    """One commit that writes `files` ({path: text}) and git-rm's `remove`; returns its sha."""
    for path, text in (files or {}).items():
        (cwd / path).parent.mkdir(parents=True, exist_ok=True)
        (cwd / path).write_text(text)
    for path in remove:
        subprocess.run(["git", "rm", "-q", path], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=cwd, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "c"], cwd=cwd, check=True, capture_output=True)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class TestNetTestDecrease:
    def test_commenting_a_test_out_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit(THREE, path="a.test.ts")
        head = commit("it('a', () => {})\n// test('b', () => {})\nit('c', () => {})\n", path="a.test.ts")
        r = run_cli(cwd, "tests", base, head)
        assert r.returncode == 1 and "a.test.ts" in r.stderr

    def test_block_commenting_a_test_out_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit(THREE, path="a.test.ts")
        head = commit("it('a', () => {})\n/*\ntest('b', () => {})\n*/\nit('c', () => {})\n", path="a.test.ts")
        assert run_cli(cwd, "tests", base, head).returncode == 1

    def test_commenting_out_a_python_test_is_a_loosening(self, repo):
        cwd, commit = repo
        base = commit("def test_a():\n    pass\ndef test_b():\n    pass\n", path="a_test.py")
        head = commit("def test_a():\n    pass\n# def test_b():\n#     pass\n", path="a_test.py")
        assert run_cli(cwd, "tests", base, head).returncode == 1

    def test_a_glob_string_is_not_a_block_comment(self, repo):
        # `/*` inside a string must not swallow the tests after it, or the deletion
        # below would count as 0 -> 0.
        cwd, commit = repo
        glob = "const files = 'src/**/*.ts'\n"
        base = commit(glob + THREE, path="a.test.ts")
        head = commit(glob + "it('a', () => {})\nit('c', () => {})\n", path="a.test.ts")
        assert run_cli(cwd, "tests", base, head).returncode == 1

    def test_deleting_a_phpunit_test_is_a_loosening(self, repo):
        cwd, commit = repo
        two = "#[Test]\npublic function addsItem(): void {}\npublic function testTotal(): void {}\n"
        base = commit(two, path="CartTest.php")
        head = commit("#[Test]\npublic function addsItem(): void {}\n", path="CartTest.php")
        assert run_cli(cwd, "tests", base, head).returncode == 1

    def test_php_test_attribute_is_not_a_comment(self, repo):
        # `#[Test]` starts with `#` but is a PHP attribute, so removing it is a deletion.
        cwd, commit = repo
        base = commit("#[Test]\npublic function addsItem(): void {}\n", path="CartTest.php")
        head = commit("public function addsItem(): void {}\n", path="CartTest.php")
        assert run_cli(cwd, "tests", base, head).returncode == 1

    @pytest.mark.parametrize("attr", ["[" + "Test]", "[" + "TestMethod]"])
    def test_deleting_an_nunit_or_mstest_test_is_a_loosening(self, repo, attr):
        cwd, commit = repo
        base = commit(f"{attr}\npublic void A() {{}}\n{attr}\npublic void B() {{}}\n", path="CartTests.cs")
        head = commit(f"{attr}\npublic void A() {{}}\n", path="CartTests.cs")
        assert run_cli(cwd, "tests", base, head).returncode == 1

    def test_splitting_a_test_file_in_two_is_safe(self, repo):
        cwd, _ = repo
        base = commit_tree(cwd, {"cart.test.ts": THREE})
        head = commit_tree(
            cwd,
            {"cart-add.test.ts": "it('a', () => {})\nit('c', () => {})\n", "cart-total.test.ts": "test('b', () => {})\n"},
            remove=["cart.test.ts"],
        )
        r = run_cli(cwd, "tests", base, head)
        assert r.returncode == 0, r.stderr

    def test_moving_a_test_between_files_is_safe(self, repo):
        cwd, _ = repo
        base = commit_tree(cwd, {"a.test.ts": THREE, "b.test.ts": "it('d', () => {})\n"})
        head = commit_tree(cwd, {"a.test.ts": "it('a', () => {})\nit('c', () => {})\n", "b.test.ts": "it('d', () => {})\ntest('b', () => {})\n"})
        assert run_cli(cwd, "tests", base, head).returncode == 0

    def test_renaming_a_test_file_is_safe(self, repo):
        cwd, commit = repo
        base = commit(THREE, path="a.test.ts")
        subprocess.run(["git", "mv", "a.test.ts", "cart.test.ts"], cwd=cwd, check=True, capture_output=True)
        head = commit_tree(cwd)
        assert run_cli(cwd, "tests", base, head).returncode == 0

    def test_tests_count_ignores_commented_tests(self, repo):
        cwd, commit = repo
        head = commit("it('a', () => {})\n// it('b', () => {})\n", path="a.test.ts")
        assert run_cli(cwd, "tests-count", head).stdout.strip() == "1"


WF = ".github/workflows/ci.yml"
WF_BASE = "jobs:\n  test:\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@aaaa\n"


class TestWorkflowApprove:
    @pytest.mark.parametrize(
        ("added", "name"),
        [
            ("      pull-requests: " + "write\n", "workflow-pr-write"),
            ("    permissions: write" + "-all\n", "workflow-pr-write"),
            ("      - run: gh pr review --" + "approve \"$PR\"\n", "workflow-approve-cli"),
            ("      - run: gh api repos/o/r/pulls/1/reviews -f event=" + "APPROVE\n", "workflow-approve-event"),
            ("      - uses: hmarr/auto-" + "approve-action@bbbb\n", "workflow-approve-action"),
        ],
    )
    def test_added_approve_capability_is_flagged(self, repo, added, name):
        cwd, commit = repo
        base = commit(WF_BASE, path=WF)
        head = commit(WF_BASE + added, path=WF)
        r = run_cli(cwd, "workflow-approve", base, head)
        assert r.returncode == 1 and name in r.stderr and WF in r.stderr

    def test_an_action_sha_bump_is_safe(self, repo):
        # Renovate rewrites the pin in place; the approve-capable line count is unchanged.
        cwd, commit = repo
        base = commit(WF_BASE + "      - uses: hmarr/auto-" + "approve-action@bbbb\n", path=WF)
        head = commit(WF_BASE + "      - uses: hmarr/auto-" + "approve-action@cccc # v4\n", path=WF)
        assert run_cli(cwd, "workflow-approve", base, head).returncode == 0

    def test_a_commented_permission_is_not_a_grant(self, repo):
        cwd, commit = repo
        base = commit(WF_BASE, path=WF)
        head = commit("#   permissions: { pull-requests: " + "write }\n" + WF_BASE, path=WF)
        assert run_cli(cwd, "workflow-approve", base, head).returncode == 0

    def test_only_workflow_files_are_scanned(self, repo):
        cwd, commit = repo
        base = commit("# docs\n", path="docs/ci.md")
        head = commit("# docs\npull-requests: " + "write\n", path="docs/ci.md")
        assert run_cli(cwd, "workflow-approve", base, head).returncode == 0
