"""Consistency checks for the web client's per-domain config.

Every domain in the switcher registry (``web/js/domain-switcher.js``) must have
a coherent web config, or the graph renders wrong while the pipeline looks fine.
This is the automated form of ``docs/guides/new-domain-features.md`` Section 7 —
it catches the drift found onboarding weapons_detection: a missing ``<slug>.json``
left every node gray, and the dashboard's inline domain list had gone stale.

Pure file/profile reads — no network, no LLM.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain import load_domain_profile  # noqa: E402

WEB = ROOT / "web"
DOMAINS_DIR = WEB / "data" / "domains"
SWITCHER = WEB / "js" / "domain-switcher.js"
ONTOLOGY_JS = WEB / "js" / "ontology.js"
DASHBOARD = WEB / "dashboard.html"

# ``Document`` is the universal source-article node type: it shows up in the
# graph for every domain, so a config may color/group it whether or not the
# domain's profile declares it as an extracted entity type (some do, some don't).
UNIVERSAL_TYPES = {"Document"}


def _slugs_from_js(path: Path) -> list[str]:
    """Pull the domain slugs out of a ``KNOWN_DOMAINS = [{ slug: '...' }]`` block."""
    return re.findall(r"slug:\s*'([a-z_]+)'", path.read_text(encoding="utf-8"))


# Collected at import time so each domain gets its own parametrized test case.
DOMAINS = _slugs_from_js(SWITCHER)


def test_switcher_registry_nonempty():
    assert DOMAINS, "no domains parsed from domain-switcher.js KNOWN_DOMAINS"


def test_registries_agree_on_domain_set():
    """The three KNOWN_DOMAINS lists — switcher, ontology page, and the
    dashboard's inline fallback — must enumerate the same domains. The dashboard
    fallback silently drifted once (stuck at ai+biosafety); this pins them."""
    switcher = set(_slugs_from_js(SWITCHER))
    ontology = set(_slugs_from_js(ONTOLOGY_JS))
    dashboard = set(_slugs_from_js(DASHBOARD))
    assert switcher == ontology, f"switcher vs ontology.js differ: {switcher ^ ontology}"
    assert switcher == dashboard, f"switcher vs dashboard fallback differ: {switcher ^ dashboard}"


@pytest.mark.parametrize("slug", DOMAINS)
def test_domain_web_config(slug):
    cfg_path = DOMAINS_DIR / f"{slug}.json"
    onto_path = DOMAINS_DIR / f"{slug}.ontology.json"
    assert cfg_path.exists(), f"missing web config web/data/domains/{slug}.json"
    assert onto_path.exists(), (
        f"missing web/data/domains/{slug}.ontology.json "
        f"— run: python scripts/export_ontology.py --domain {slug}"
    )

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    onto = json.loads(onto_path.read_text(encoding="utf-8"))
    profile = load_domain_profile(slug)

    profile_types = set(profile["entity_types"])
    cfg_types = set(cfg["entityTypes"])
    onto_types = {e["name"] for e in onto["entityTypes"]}
    colors = cfg.get("typeColors", {})
    grouped = [t for g in cfg.get("typeGroups", []) for t in g["types"]]
    allowed = cfg_types | UNIVERSAL_TYPES

    # The web config declares exactly the domain profile's entity types.
    assert cfg_types == profile_types, (
        f"{slug}: config entityTypes disagree with the domain profile — "
        f"only-in-config={sorted(cfg_types - profile_types)}, "
        f"only-in-profile={sorted(profile_types - cfg_types)}"
    )
    # The generated ontology matches the config it was built from.
    assert onto_types == cfg_types, (
        f"{slug}: ontology entityTypes drift from config {sorted(onto_types ^ cfg_types)} "
        f"— regenerate: python scripts/export_ontology.py --domain {slug}"
    )
    # Every declared type has a color (else it renders gray).
    no_color = [t for t in cfg["entityTypes"] if t not in colors]
    assert not no_color, f"{slug}: entityTypes without a typeColors entry (render gray): {no_color}"
    # Colors and groups reference only declared (or universal) types.
    bad_colors = [t for t in colors if t not in allowed]
    assert not bad_colors, f"{slug}: typeColors for unknown types: {bad_colors}"
    bad_group = [t for t in grouped if t not in allowed]
    assert not bad_group, f"{slug}: typeGroups reference unknown types: {bad_group}"
    # Every declared type appears in exactly one legend group.
    orphaned = [t for t in cfg["entityTypes"] if t not in grouped]
    duplicated = [t for t in set(grouped) if grouped.count(t) > 1 and t in cfg_types]
    assert not orphaned, f"{slug}: entityTypes not in any typeGroup (missing from legend): {orphaned}"
    assert not duplicated, f"{slug}: entityTypes in multiple typeGroups: {duplicated}"
    # The ontology's per-type colors stay in sync with the config.
    stale = [
        e["name"] for e in onto["entityTypes"]
        if e["name"] in colors and e["color"] != colors[e["name"]]
    ]
    assert not stale, (
        f"{slug}: ontology colors out of sync with config {stale} "
        f"— regenerate: python scripts/export_ontology.py --domain {slug}"
    )
    # The slug is present in all three registries.
    for reg in (SWITCHER, ONTOLOGY_JS, DASHBOARD):
        assert slug in reg.read_text(encoding="utf-8"), f"{slug}: missing from {reg.name}"
