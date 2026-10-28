"""The scripts pin in the mise templates: every template agrees on one FOUNDRY_SCRIPTS_REF,
every script it fetches exists in scripts/, and cut-release.sh points the pin and the
per-script sha256 lines at the tag it cuts. A tag whose templates pin an older ref fetches
that ref's scripts/, which 404s on any script added since (v2.13.0 pinned v2.12.0, which
had no codemap-check); a stale digest fails every fetch closed.
"""
import hashlib
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = sorted((ROOT / "mise").glob("*.toml"))
# Resolved through PATH: a bare "bash" on Windows hits System32's WSL launcher first.
BASH = shutil.which("bash") or "bash"
DIGEST_LINE = re.compile(r"^([\w./-]+) ([0-9a-f]{64})$", re.M)


def digests(text: str) -> dict[str, str]:
    return dict(DIGEST_LINE.findall(text))


def load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def repo_path(name: str) -> str:
    """A digest line names scripts/<name>, or a repo path when it has a slash."""
    return name if "/" in name else f"scripts/{name}"


def fetch_list(template: dict) -> list[str]:
    names = list(digests(template["tasks"]["setup:foundry-scripts"]["run"]))
    assert names, "setup:foundry-scripts has no '<script> <sha256>' lines"
    return names


def test_templates_agree_on_one_scripts_ref():
    refs = {p.name: load(p)["env"]["FOUNDRY_SCRIPTS_REF"] for p in TEMPLATES}
    assert len(set(refs.values())) == 1, refs


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_every_fetched_script_exists(path):
    missing = [s for s in fetch_list(load(path)) if not (ROOT / repo_path(s)).is_file()]
    assert not missing, f"{path.name} fetches files the repo does not have: {missing}"


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_cut_release_pins_ref_and_digests_to_the_new_tag(tmp_path):
    shutil.copytree(ROOT / "mise", tmp_path / "mise")
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "presets" / "rules", tmp_path / "presets" / "rules")
    # Stale digests, as after a release that changed a script: the rewrite must replace them.
    for p in (tmp_path / "mise").glob("*.toml"):
        p.write_text(DIGEST_LINE.sub(lambda m: f"{m[1]} {'0' * 64}", p.read_text(encoding="utf-8")),
                     encoding="utf-8", newline="\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed")
    before = {p.name: p.read_text(encoding="utf-8") for p in (tmp_path / "mise").glob("*.toml")}
    # cut-release.sh reads its bump from $1 at top level, so give it one before sourcing.
    script = (ROOT / "scripts" / "cut-release.sh").as_posix()
    subprocess.run(
        [BASH, "-c", f'set -- patch; source "{script}"; pin_foundry_scripts v9.9.9'],
        cwd=tmp_path, check=True,
    )
    for name, old in before.items():
        new = (tmp_path / "mise" / name).read_text(encoding="utf-8")
        assert load(tmp_path / "mise" / name)["env"]["FOUNDRY_SCRIPTS_REF"] == "v9.9.9", name
        got = digests(new)
        assert got.keys() == digests(old).keys(), name
        for s, d in got.items():
            assert d == hashlib.sha256((ROOT / repo_path(s)).read_bytes()).hexdigest(), (name, s)
        # Only the pin and digest lines move: the comments and the rest stay.
        assert len(old.splitlines()) == len(new.splitlines()), name
        changed = [b for a, b in zip(old.splitlines(), new.splitlines()) if a != b]
        assert all(c == 'FOUNDRY_SCRIPTS_REF = "v9.9.9"' or DIGEST_LINE.fullmatch(c) for c in changed), name
