"""FOUNDRY_SCRIPTS_REF is not Renovate's to bump: a bump without that tag's digest lines
fails setup:foundry-scripts closed, and Renovate cannot compute them. Consumers keep the
old `# renovate:` annotation (templates never reach them again), so the preset itself must
switch it off, while the reusable-workflow refs stay tracked.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRESET = json.loads((ROOT / "presets" / "renovate.json").read_text(encoding="utf-8"))
LEGACY_PIN = '# renovate: datasource=github-tags depName=CMaintz/foundry\nFOUNDRY_SCRIPTS_REF = "v2.13.0"\n'


def annotation_deps(text: str) -> list[tuple[str, str]]:
    """(datasource, depName) for each pin the preset's annotation manager would extract."""
    deps = []
    for m in PRESET["customManagers"]:
        for s in m["matchStrings"]:
            for hit in re.finditer(s.replace("(?<", "(?P<"), text):
                g = hit.groupdict()
                if "depName" in g:
                    deps.append((g["datasource"], g["depName"]))
    return deps


def enabled(manager: str, package: str) -> bool:
    """Renovate applies every matching rule in order, so the last `enabled` wins."""
    on = True
    for r in PRESET["packageRules"]:
        if manager not in r.get("matchManagers", [manager]):
            continue
        if not {"*", package} & set(r.get("matchPackageNames", ["*"])):
            continue
        on = r.get("enabled", on)
    return on


def test_templates_do_not_annotate_the_scripts_ref():
    for p in sorted((ROOT / "mise").glob("*.toml")):
        assert ("github-tags", "CMaintz/foundry") not in annotation_deps(p.read_text(encoding="utf-8")), p.name


def test_a_consumer_still_carrying_the_annotation_is_not_bumped():
    assert annotation_deps(LEGACY_PIN) == [("github-tags", "CMaintz/foundry")]
    assert not enabled("custom.regex", "CMaintz/foundry")


def test_reusable_workflow_refs_stay_tracked():
    assert enabled("github-actions", "CMaintz/foundry")
    # The annotation manager still tracks other pins, such as the Python template's tools.
    assert enabled("custom.regex", "mypy")
