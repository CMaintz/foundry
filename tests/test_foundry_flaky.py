"""Tests for scripts/foundry-flaky: report parsing, gate decision + streak logging,
the live rerun/classify loop (synthetic command), and cross-run auto-prune.

The rerun loop is exercised with a synthetic command, not vitest/Gradle - so flip/real
classification and the shell-quoting contract are validated, but the runner-filter
semantics (`vitest -t`, `gradlew --tests`) remain unverified. See designs/flake-triager.md.
"""
import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "foundry-flaky"
# The script has no .py extension, so give importlib an explicit source loader.
_loader = SourceFileLoader("foundry_flaky", str(SCRIPT))
_spec = importlib.util.spec_from_loader("foundry_flaky", _loader)
flaky = importlib.util.module_from_spec(_spec)
_loader.exec_module(flaky)


JUNIT = """<testsuite name="s">
  <testcase classname="com.foo.BarTest" name="passes"/>
  <testcase classname="com.foo.BarTest" name="fails"><failure>boom</failure></testcase>
</testsuite>"""

VITEST = json.dumps({
    "testResults": [{
        "assertionResults": [
            {"fullName": "cart adds an item", "status": "passed"},
            {"fullName": "cart recalculates total after concurrent add", "status": "failed"},
        ]
    }]
})


class TestParse:
    def test_junit_file(self, tmp_path):
        p = tmp_path / "r.xml"; p.write_text(JUNIT)
        failed, total, all_ids = flaky.parse_report(str(p))
        assert total == 2
        assert failed == ["com.foo.BarTest.fails"]
        assert "com.foo.BarTest.passes" in all_ids

    def test_vitest_file(self, tmp_path):
        p = tmp_path / "r.json"; p.write_text(VITEST)
        failed, total, all_ids = flaky.parse_report(str(p))
        assert total == 2
        assert failed == ["cart recalculates total after concurrent add"]

    def test_directory_of_junit_is_merged(self, tmp_path):
        d = tmp_path / "test-results"; d.mkdir()
        (d / "TEST-a.xml").write_text(
            '<testsuite><testcase classname="A" name="ok"/></testsuite>')
        (d / "TEST-b.xml").write_text(
            '<testsuite><testcase classname="B" name="no"><error>x</error></testcase></testsuite>')
        failed, total, all_ids = flaky.parse_report(str(d))
        assert total == 2 and failed == ["B.no"] and set(all_ids) == {"A.ok", "B.no"}

    def test_empty_directory_errors(self, tmp_path):
        d = tmp_path / "empty"; d.mkdir()
        with pytest.raises(SystemExit):
            flaky.parse_report(str(d))


def _baseline(tmp_path, *ids):
    p = tmp_path / "flaky-baseline.json"
    p.write_text(json.dumps({"quarantined": [{"id": i, "reason": "r", "since": "s"} for i in ids]}))
    return p


class TestGateAndStreak:
    def test_real_failure_gates(self, tmp_path, capsys):
        rep = tmp_path / "r.xml"; rep.write_text(JUNIT)
        assert flaky.cmd_gate(str(rep), None) == 1  # fails not quarantined

    def test_quarantined_failure_does_not_gate(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rep = tmp_path / "r.xml"; rep.write_text(JUNIT)
        base = _baseline(tmp_path, "com.foo.BarTest.fails")
        assert flaky.cmd_gate(str(rep), str(base)) == 0

    def test_gate_appends_streak_for_quarantined_that_ran(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rep = tmp_path / "r.xml"; rep.write_text(JUNIT)
        # Quarantine one passing and one failing test; both ran.
        base = _baseline(tmp_path, "com.foo.BarTest.passes", "com.foo.BarTest.fails")
        flaky.cmd_gate(str(rep), str(base))
        log = (tmp_path / ".foundry" / "flaky-streaks.jsonl").read_text().splitlines()
        assert len(log) == 1
        res = json.loads(log[0])["results"]
        assert res == {"com.foo.BarTest.passes": "pass", "com.foo.BarTest.fails": "fail"}

    def test_no_streak_line_without_baseline(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        rep = tmp_path / "r.xml"; rep.write_text(JUNIT)
        flaky.cmd_gate(str(rep), None)
        assert not (tmp_path / ".foundry" / "flaky-streaks.jsonl").exists()


class TestTrailingGreenAndPrune:
    def _log(self, tmp_path, *runs):
        """runs: dicts of {id: 'pass'|'fail'} oldest->newest."""
        p = tmp_path / "streaks.jsonl"
        p.write_text("".join(json.dumps({"ts": i, "results": r}) + "\n" for i, r in enumerate(runs)))
        return p

    def test_consecutive_passes_counted(self, tmp_path):
        log = self._log(tmp_path, {"t": "pass"}, {"t": "pass"}, {"t": "pass"})
        assert flaky.trailing_green(str(log), "t") == 3

    def test_fail_resets_streak(self, tmp_path):
        log = self._log(tmp_path, {"t": "pass"}, {"t": "fail"}, {"t": "pass"}, {"t": "pass"})
        assert flaky.trailing_green(str(log), "t") == 2

    def test_absent_run_is_skipped_not_a_break(self, tmp_path):
        log = self._log(tmp_path, {"t": "pass"}, {"other": "fail"}, {"t": "pass"})
        assert flaky.trailing_green(str(log), "t") == 2

    def test_missing_log_is_zero(self, tmp_path):
        assert flaky.trailing_green(str(tmp_path / "nope.jsonl"), "t") == 0

    def test_prune_removes_only_stable_entries(self, tmp_path, capsys):
        base = _baseline(tmp_path, "stable", "still-flaky")
        log = self._log(tmp_path, *([{"stable": "pass", "still-flaky": "pass"}] * 9),
                        {"stable": "pass", "still-flaky": "fail"})
        # stable: 10 trailing greens; still-flaky: reset to 0 by the last fail.
        assert flaky.cmd_prune(str(base), 10, str(log)) == 0
        kept = [e["id"] for e in json.loads(base.read_text())["quarantined"]]
        assert kept == ["still-flaky"]
        assert "pruned: stable" in capsys.readouterr().out

    def test_prune_noop_when_none_qualify(self, tmp_path):
        base = _baseline(tmp_path, "t")
        log = self._log(tmp_path, {"t": "pass"}, {"t": "pass"})
        assert flaky.cmd_prune(str(base), 10, str(log)) == 0
        assert [e["id"] for e in json.loads(base.read_text())["quarantined"]] == ["t"]


class TestClassifyLiveRerun:
    """Drive the real subprocess rerun loop with a synthetic command, using an id that
    contains spaces to prove the rerun template's quoting contract."""

    FLAKY_ID = "cart recalculates total after concurrent add"

    def _report(self, tmp_path, tid):
        p = tmp_path / "r.json"
        p.write_text(json.dumps({"testResults": [{"assertionResults": [
            {"fullName": tid, "status": "failed"}]}]}))
        return p

    def test_flipping_test_is_a_flake(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        counter = tmp_path / "n"
        # flip.py: errors (exit 3) if the id was not passed as ONE arg (quoting broke),
        # else alternates pass/fail across runs -> a flake.
        (tmp_path / "flip.py").write_text(
            "import sys\n"
            "from pathlib import Path\n"
            "sys.exit(3) if len(sys.argv) != 2 else None\n"
            "p = Path('n'); i = int(p.read_text() or '0'); p.write_text(str(i + 1))\n"
            "sys.exit(i % 2)\n")
        counter.write_text("0")
        rep = self._report(tmp_path, self.FLAKY_ID)
        tmpl = 'python flip.py "{test}"'  # {test} MUST be quoted: the id has spaces
        flaky.cmd_classify(str(rep), None, 4, tmpl)
        out = capsys.readouterr().out
        assert "-> FLAKE" in out and self.FLAKY_ID in out

    def test_always_failing_test_is_real(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "fail.py").write_text("import sys\nsys.exit(1)\n")
        rep = self._report(tmp_path, "always broken")
        flaky.cmd_classify(str(rep), None, 3, 'python fail.py "{test}"')
        out = capsys.readouterr().out
        assert "-> real" in out
