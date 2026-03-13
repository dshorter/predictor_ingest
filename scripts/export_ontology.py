"""Export domain ontology as structured JSON for the web ontology page.

Reads the active domain profile (via PREDICTOR_DOMAIN env var) and emits
a rich JSON file to web/data/domains/{slug}.ontology.json that the
ontology.html page can load without a backend.

Usage:
    python scripts/export_ontology.py [--domain biosafety]
    make export_ontology DOMAIN=biosafety
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from domain import get_active_profile  # noqa: E402


# Human-readable group labels for ontology display
GROUP_LABELS = {
    # AI domain
    "document":      "Document",
    "org_person":    "Org / Person / Program",
    "tech_model":    "Tech / Model / Tool / Dataset",
    "forecasting":   "Forecasting",
    # Biosafety domain
    "regulatory":    "Regulatory & Governance",
    "research":      "Research & Science",
    "containment":   "Containment & Operations",
    "incident":      "Incident & Response",
    "capability":    "Capability & Threat",
    "organizational": "Organizational",
}


def export_ontology(domain_slug: str, output_dir: Path) -> Path:
    profile = get_active_profile()

    canonical: list[str] = profile["relation_taxonomy"]["canonical"]
    normalization: dict[str, str] = profile["relation_taxonomy"].get("normalization", {})
    groups: dict[str, list[str]] = profile["relation_taxonomy"].get("groups", {})

    # Build reverse map: canonical → sorted list of aliases
    aliases_by_canonical: dict[str, list[str]] = {}
    for alias, canon in normalization.items():
        aliases_by_canonical.setdefault(canon, []).append(alias)
    for k in aliases_by_canonical:
        aliases_by_canonical[k].sort()

    # Relations that belong to at least one group
    grouped_rels: set[str] = {r for rels in groups.values() for r in rels}

    relation_groups = [
        {
            "key": group_key,
            "label": GROUP_LABELS.get(group_key, group_key.replace("_", " ").title()),
            "relations": [
                {
                    "rel": rel,
                    "isBase": rel == profile.get("base_relation"),
                    "aliases": aliases_by_canonical.get(rel, []),
                }
                for rel in rels
            ],
        }
        for group_key, rels in groups.items()
    ]

    # Any canonical relations not in any group (safety net)
    ungrouped = [r for r in canonical if r not in grouped_rels]

    # Entity types — enrich with prefix and color from domain config
    id_prefixes: dict[str, str] = profile.get("id_prefixes", {})

    domain_config_path = (
        Path(__file__).resolve().parents[1]
        / "web" / "data" / "domains" / f"{domain_slug}.json"
    )
    type_colors: dict[str, str] = {}
    type_groups: list[dict] = []
    if domain_config_path.exists():
        with open(domain_config_path, encoding="utf-8") as fh:
            dc = json.load(fh)
        type_colors = dc.get("typeColors", {})
        type_groups = dc.get("typeGroups", [])

    entity_types = [
        {
            "name": et,
            "prefix": id_prefixes.get(et, et.lower()),
            "canonicalIdPattern": f"{id_prefixes.get(et, et.lower())}:{{slug}}",
            "color": type_colors.get(et, "#9CA3AF"),
        }
        for et in profile["entity_types"]
    ]

    ontology = {
        "domain": profile["domain"],
        "baseRelation": profile.get("base_relation", "MENTIONS"),
        "entityTypes": entity_types,
        "typeGroups": type_groups,
        "relationGroups": relation_groups,
        "ungroupedRelations": ungrouped,
        "normalization": normalization,
        "qualityThresholds": profile.get("quality_thresholds", {}),
        "gateThresholds": profile.get("gate_thresholds", {}),
        "scoringWeights": profile.get("scoring_weights", {}),
        "escalationThreshold": profile.get("escalation_threshold", 0.6),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{domain_slug}.ontology.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(ontology, fh, indent=2, ensure_ascii=False)

    n_classes = len(entity_types)
    n_rels = len(canonical)
    n_aliases = len(normalization)
    print(
        f"Ontology exported → {output_path}\n"
        f"  {n_classes} classes · {n_rels} object properties · {n_aliases} normalization aliases"
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", default=None, help="Domain slug (default: PREDICTOR_DOMAIN or 'ai')")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: web/data/domains/)",
    )
    args = parser.parse_args()

    domain_slug = args.domain or os.environ.get("PREDICTOR_DOMAIN", "ai")
    os.environ["PREDICTOR_DOMAIN"] = domain_slug

    output_dir = Path(args.output_dir) if args.output_dir else (
        Path(__file__).resolve().parents[1] / "web" / "data" / "domains"
    )

    export_ontology(domain_slug, output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
