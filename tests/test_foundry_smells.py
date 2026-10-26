"""Tests for scripts/foundry-smells: the smell-count reducer, sibling resolution,
sidecar writing, and the sensors|mapper orchestration (exit precedence, fail-closed).

The real sensors/mapper pipeline is exercised by hand against an installed habit-hooks
venv; here the orchestration is driven through a monkeypatched subprocess so exit
precedence and fail-closed behaviour are deterministic and cross-platform. See
designs/loop-telemetry.md.
"""
import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "foundry-smells"
_loader = SourceFileLoader("foundry_smells", str(SCRIPT))
_spec = importlib.util.spec_from_loader("foundry_smells", _loader)
smells = importlib.util.module_from_spec(_spec)
_loader.exec_module(smells)


class TestCounts:
    def test_counts_occurrences_per_smell(self):
        findings = [
            {"smell": "oversized-file", "issues": [
                {"key": "a.ts", "details": {"file": "a.ts"}},
                {"key": "b.ts", "details": {"file": "b.ts"}},
            ]},
            {"smell": "high-complexity", "issues": [{"key": "c.ts", "details": {"file": "c.ts"}}]},
        ]
        assert smells.counts(findings) == {"oversized-file": 2, "high-complexity": 1}

    def test_same_smell_same_place_from_two_sensors_counts_once(self):
        # line-count and an eslint max-lines both flag one file; merged_findings keys on
        # (smell, key, place), so it is one occurrence, not two.
        findings = [
            {"smell": "oversized-file", "issues": [{"key": "a.ts", "details": {"file": "a.ts", "line": None}}]},
            {"smell": "oversized-file", "issues": [{"key": "a.ts", "details": {"file": "a.ts", "line": None}}]},
        ]
        assert smells.counts(findings) == {"oversized-file": 1}

    def test_same_key_different_place_counts_twice(self):
        # Two clones of one file name a RANGE: different startLine -> two occurrences.
        findings = [{"smell": "duplicated-code", "issues": [
            {"key": "a.ts", "details": {"file": "a.ts", "startLine": 10}},
            {"key": "a.ts", "details": {"file": "a.ts", "startLine": 80}},
        ]}]
        assert smells.counts(findings) == {"duplicated-code": 2}

    def test_incomplete_run_is_kept(self):
        # A broken sensor is real signal, not noise: loop-report, not the reducer,
        # decides to exclude a partial run from the trend.
        findings = [{"smell": "incomplete-run", "issues": [{"key": "jscpd failed", "details": {}}]}]
        assert smells.counts(findings) == {"incomplete-run": 1}

    def test_finding_without_smell_is_skipped(self):
        assert smells.counts([{"issues": [{"key": "x"}]}]) == {}


class TestSibling:
    def test_resolves_plain_sibling(self, tmp_path):
        (tmp_path / "habit-sensors").write_text("")
        got = smells.sibling(str(tmp_path / "habit-hooks"), "habit-sensors")
        assert got == str(tmp_path / "habit-sensors")

    def test_resolves_exe_sibling(self, tmp_path):
        (tmp_path / "habit-mapper.exe").write_text("")
        got = smells.sibling(str(tmp_path / "habit-hooks.exe"), "habit-mapper")
        assert got == str(tmp_path / "habit-mapper.exe")

    def test_falls_back_to_bare_name(self, tmp_path):
        assert smells.sibling(str(tmp_path / "habit-hooks"), "habit-sensors") == "habit-sensors"


class TestWriteSidecar:
    def test_writes_compact_one_line_lf(self, tmp_path, monkeypatch):
        target = tmp_path / "sub" / "smells.json"
        monkeypatch.setenv("FOUNDRY_SMELLS", str(target))
        smells.write_sidecar({"b": 2, "a": 1})
        raw = target.read_bytes()
        assert b"\r\n" not in raw
        assert raw == b'{"a":1,"b":2}\n'  # sorted, no spaces, single line

    def test_oserror_is_swallowed(self, tmp_path, monkeypatch):
        # A directory where the file should be: open() raises, but the gate must not.
        bad = tmp_path / "smells.json"
        bad.mkdir()
        monkeypatch.setenv("FOUNDRY_SMELLS", str(bad))
        smells.write_sidecar({"a": 1})  # must not raise


class _Fake:
    """A fake subprocess.run keyed on the command's basename, returning canned
    CompletedProcess-likes for the sensors and mapper legs."""
    def __init__(self, sensors_out=b"[]", sensors_rc=0, mapper_rc=0, raise_on=None):
        self.sensors_out, self.sensors_rc = sensors_out, sensors_rc
        self.mapper_rc, self.raise_on = mapper_rc, raise_on
        self.mapper_input = None

    def __call__(self, cmd, **kwargs):
        name = Path(cmd[0]).name
        if self.raise_on and self.raise_on in name:
            raise FileNotFoundError(f"no {name}")
        if "sensors" in name:
            return _Completed(stdout=self.sensors_out, stderr=b"", returncode=self.sensors_rc)
        self.mapper_input = kwargs.get("input")
        return _Completed(stdout=None, stderr=None, returncode=self.mapper_rc)


class _Completed:
    def __init__(self, stdout, stderr, returncode):
        self.stdout, self.stderr, self.returncode = stdout, stderr, returncode


def _run(monkeypatch, tmp_path, fake, args=("--branch", "base")):
    monkeypatch.setenv("FOUNDRY_SMELLS", str(tmp_path / "smells.json"))
    monkeypatch.setattr(smells.subprocess, "run", fake)
    return smells.main([str(tmp_path / "habit-hooks"), *args])


class TestOrchestration:
    def test_exit_is_sensors_rc_when_mapper_clean(self, tmp_path, monkeypatch):
        # A clean mapper over a failed sensor still fails: mapper.rc(0) or sensors.rc(2).
        assert _run(monkeypatch, tmp_path, _Fake(sensors_rc=2, mapper_rc=0)) == 2

    def test_exit_is_mapper_rc_when_nonzero(self, tmp_path, monkeypatch):
        assert _run(monkeypatch, tmp_path, _Fake(sensors_rc=0, mapper_rc=1)) == 1

    def test_exit_zero_when_both_clean(self, tmp_path, monkeypatch):
        assert _run(monkeypatch, tmp_path, _Fake(sensors_rc=0, mapper_rc=0)) == 0

    def test_sidecar_written_from_findings(self, tmp_path, monkeypatch):
        out = json.dumps([{"smell": "oversized-file", "issues": [{"key": "a", "details": {"file": "a"}}]}]).encode()
        _run(monkeypatch, tmp_path, _Fake(sensors_out=out))
        assert json.loads((tmp_path / "smells.json").read_text()) == {"oversized-file": 1}

    def test_sensor_stdout_is_piped_to_mapper(self, tmp_path, monkeypatch):
        out = b'[{"smell": "x", "issues": []}]'
        fake = _Fake(sensors_out=out)
        _run(monkeypatch, tmp_path, fake)
        assert fake.mapper_input == out  # mapper sees exactly what the sensors emitted

    def test_invalid_sensor_json_writes_no_sidecar_but_still_maps(self, tmp_path, monkeypatch):
        rc = _run(monkeypatch, tmp_path, _Fake(sensors_out=b"not json", mapper_rc=1))
        assert rc == 1  # mapper still ran
        assert not (tmp_path / "smells.json").exists()

    @pytest.mark.parametrize("bad", [
        b"[1, 2, 3]",  # list of non-dicts -> finding.get raises AttributeError
        b'[{"smell": "x", "issues": [{"key": "k", "details": {"line": [1, 2]}}]}]',  # unhashable place
        # mixed str + non-string smell keys -> json.dumps(sort_keys=True) raises TypeError
        b'[{"smell": "a", "issues": [{"key": "k1", "details": {}}]},'
        b' {"smell": 5, "issues": [{"key": "k2", "details": {}}]}]',
    ])
    def test_wrong_shape_sensor_json_never_crashes_the_gate(self, tmp_path, monkeypatch, bad):
        # Telemetry is best-effort: valid JSON of an unexpected shape must not abort the
        # run before the mapper, and must not write a sidecar.
        rc = _run(monkeypatch, tmp_path, _Fake(sensors_out=bad, sensors_rc=0, mapper_rc=0))
        assert rc == 0
        assert not (tmp_path / "smells.json").exists()

    def test_empty_sensor_stdout_writes_no_sidecar(self, tmp_path, monkeypatch):
        # A dead sensors stage (no output) must not read as a clean zero-smell scan.
        _run(monkeypatch, tmp_path, _Fake(sensors_out=b"", sensors_rc=2))
        assert not (tmp_path / "smells.json").exists()

    def test_clean_scan_writes_empty_object(self, tmp_path, monkeypatch):
        # `[]` IS a run (ran, found nothing) -> `{}`, distinct from the dead-sensor case.
        _run(monkeypatch, tmp_path, _Fake(sensors_out=b"[]"))
        assert json.loads((tmp_path / "smells.json").read_text()) == {}

    def test_missing_sensor_binary_fails_closed(self, tmp_path, monkeypatch, capsys):
        rc = _run(monkeypatch, tmp_path, _Fake(raise_on="sensors"))
        assert rc == 1
        assert "cannot run" in capsys.readouterr().err  # a line, not a traceback

    def test_no_args_usage_error(self):
        assert smells.main([]) == 2
