"""The scripts pin in the mise templates: every template agrees on one FOUNDRY_SCRIPTS_REF,
every script it fetches exists in scripts/, and cut-release.sh points the pin at the tag it
cuts. A tag whose templates pin an older ref fetches that ref's scripts/, which 404s on any
script added since (v2.13.0 pinned v2.12.0, which had no codemap-check).
"""
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


def fetch_list(template: dict) -> list[str]:
    body = template["tasks"]["setup:foundry-scripts"]["run"]
    m = re.search(r'^scripts="([^"]+)"', body, re.M)
    assert m, "setup:foundry-scripts has no scripts=\"...\" line"
    return m.group(1).split()


def load(path: Path) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def test_templates_agree_on_one_scripts_ref():
    refs = {p.name: load(p)["env"]["FOUNDRY_SCRIPTS_REF"] for p in TEMPLATES}
    assert len(set(refs.values())) == 1, refs


@pytest.mark.parametrize("path", TEMPLATES, ids=lambda p: p.stem)
def test_every_fetched_script_exists(path):
    missing = [s for s in fetch_list(load(path)) if not (ROOT / "scripts" / s).is_file()]
    assert not missing, f"{path.name} fetches scripts not in scripts/: {missing}"


def test_cut_release_pins_every_template_to_the_new_tag(tmp_path):
    shutil.copytree(ROOT / "mise", tmp_path / "mise")
    before = {p.name: p.read_text(encoding="utf-8") for p in (tmp_path / "mise").glob("*.toml")}
    # cut-release.sh reads its bump from $1 at top level, so give it one before sourcing.
    script = (ROOT / "scripts" / "cut-release.sh").as_posix()
    subprocess.run(
        [BASH, "-c", f'set -- patch; source "{script}"; pin_scripts_ref v9.9.9'],
        cwd=tmp_path, check=True,
    )
    for name, old in before.items():
        new = (tmp_path / "mise" / name).read_text(encoding="utf-8")
        assert load(tmp_path / "mise" / name)["env"]["FOUNDRY_SCRIPTS_REF"] == "v9.9.9", name
        # Only the pin line moves: the renovate annotation above it and every other line stay.
        changed = [b for a, b in zip(old.splitlines(), new.splitlines()) if a != b]
        assert changed == ['FOUNDRY_SCRIPTS_REF = "v9.9.9"'], name
        assert len(old.splitlines()) == len(new.splitlines()), name
