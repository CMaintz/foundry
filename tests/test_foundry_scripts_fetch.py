"""setup:foundry-scripts in every mise template: the cached gate scripts are checked against
the template's sha256 on every run, a bad cache entry is re-fetched, and a download that
does not match is refused. The task body runs under POSIX sh with a fake `curl` on PATH
that serves files from a directory, so no network is touched.
"""
import hashlib
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = sorted((ROOT / "mise").glob("*.toml"))
# Resolved through PATH: a bare name on Windows can hit System32's WSL launcher first.
SH = shutil.which("sh") or "sh"
DIGEST_LINE = re.compile(r"^([\w./-]+) [0-9a-f]{64}$", re.M)

FAKE_CURL = """#!/bin/sh
# Minimal stand-in for `curl -fsSL <url> -o <file>`: serve the url's path below the ref
# (scripts/x, presets/rules/y) from $FAKE_SERVED.
[ -n "${FAKE_OFFLINE:-}" ] && exit 7
url="" out=""
while [ $# -gt 0 ]; do
  case "$1" in -o) out="$2"; shift 2 ;; -*) shift ;; *) url="$1"; shift ;; esac
done
src="$FAKE_SERVED/${url#*/v0.0.0-test/}"
[ -f "$src" ] || exit 22
cat "$src" > "$out"
"""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def served_path(name: str) -> str:
    """Where a digest line's file lives in the repo: a bare name is under scripts/."""
    return name if "/" in name else f"scripts/{name}"


def served_bytes(name: str) -> bytes:
    return f"#!/bin/sh\necho {name}\n".encode()


class Fetch:
    """One template's setup:foundry-scripts body, with its digests pointed at the fake files."""

    def __init__(self, template: Path, tmp: Path):
        body = tomllib.loads(template.read_text(encoding="utf-8"))["tasks"]["setup:foundry-scripts"]["run"]
        self.names = DIGEST_LINE.findall(body)
        assert self.names, f"{template.name}: no '<script> <sha256>' lines in setup:foundry-scripts"
        self.body = DIGEST_LINE.sub(lambda m: f"{m[1]} {sha256(served_bytes(m[1]))}", body)
        self.home = tmp / "home"
        self.served = tmp / "served"
        bin_dir = tmp / "bin"
        for d in (self.home, self.served, bin_dir):
            d.mkdir()
        for n in self.names:
            served = self.served / served_path(n)
            served.parent.mkdir(parents=True, exist_ok=True)
            served.write_bytes(served_bytes(n))
        (bin_dir / "curl").write_text(FAKE_CURL, encoding="utf-8", newline="\n")
        (bin_dir / "curl").chmod(0o755)
        self.env = {**os.environ, "HOME": str(self.home), "FOUNDRY_SCRIPTS_REF": "v0.0.0-test",
                    "FAKE_SERVED": str(self.served), "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
        self.dst = self.home / ".local" / "opt" / "foundry-scripts-v0.0.0-test"

    def run(self, **env) -> subprocess.CompletedProcess:
        return subprocess.run([SH, "-c", self.body], env={**self.env, **env},
                              capture_output=True, text=True)

    def cached(self, name: str) -> bytes:
        return (self.dst / Path(name).name).read_bytes()


@pytest.fixture(params=TEMPLATES, ids=lambda p: p.stem)
def fetch(request, tmp_path):
    return Fetch(request.param, tmp_path)


def test_cold_cache_fetches_every_script(fetch):
    r = fetch.run()
    assert r.returncode == 0, r.stderr
    for n in fetch.names:
        assert fetch.cached(n) == served_bytes(n)


def test_corrupt_cached_script_is_refetched(fetch):
    # A truncated download from an earlier run must not stick in the cache forever.
    fetch.dst.mkdir(parents=True)
    victim = fetch.names[0]
    (fetch.dst / Path(victim).name).write_bytes(served_bytes(victim)[:5])
    r = fetch.run()
    assert r.returncode == 0, r.stderr
    assert fetch.cached(victim) == served_bytes(victim)


def test_download_that_does_not_match_fails_closed(fetch):
    victim = fetch.names[-1]
    (fetch.served / served_path(victim)).write_bytes(b"<html>Sign in to the Wi-Fi</html>")
    r = fetch.run()
    assert r.returncode != 0
    assert victim in r.stderr and "sha256" in r.stderr
    # Nothing unverified is left where PATH or a later run would pick it up.
    assert not (fetch.dst / Path(victim).name).exists()
    assert sorted(p.name for p in fetch.dst.iterdir()) == sorted(Path(n).name for n in fetch.names[:-1])


def test_verified_cache_needs_no_network(fetch):
    assert fetch.run().returncode == 0
    r = fetch.run(FAKE_OFFLINE="1")
    assert r.returncode == 0, r.stderr
