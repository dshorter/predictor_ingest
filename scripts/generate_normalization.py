#!/usr/bin/env python3
"""Generate mechanical tense-variant normalization entries for a domain.

Reads the canonical relation list from a domain.yaml and generates:
  - Past-tense forms (STORES → STORED)
  - Gerund forms (STORES → STORING)
  - Base/infinitive forms (STORES → STORE)
  - _BY inversions (OPERATES → OPERATED_BY)

The key insight: canonical relations are already inflected (third-person
present "STORES", past tense "CREATED", etc.). We must stem to the base
verb first, then generate all tense variants from that base.

Entries that collide with existing semantic synonyms or other canonical
types are skipped and flagged for manual review.

Usage:
    # Preview what would be generated (dry run, default)
    python scripts/generate_normalization.py domains/biosafety/domain.yaml

    # Write generated entries back into domain.yaml
    python scripts/generate_normalization.py domains/biosafety/domain.yaml --apply

    # Show only new entries (not already in the normalization map)
    python scripts/generate_normalization.py domains/biosafety/domain.yaml --new-only
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


# --- Irregular verb table ---
# base → (past, gerund, third_person)
# Only verbs likely to appear in relation names.
IRREGULARS: dict[str, tuple[str, str, str]] = {
    "BUILD": ("BUILT", "BUILDING", "BUILDS"),
    "BUY": ("BOUGHT", "BUYING", "BUYS"),
    "CUT": ("CUT", "CUTTING", "CUTS"),
    "FIND": ("FOUND", "FINDING", "FINDS"),
    "GET": ("GOT", "GETTING", "GETS"),
    "GIVE": ("GAVE", "GIVING", "GIVES"),
    "GO": ("WENT", "GOING", "GOES"),
    "HAVE": ("HAD", "HAVING", "HAS"),
    "HOLD": ("HELD", "HOLDING", "HOLDS"),
    "KEEP": ("KEPT", "KEEPING", "KEEPS"),
    "KNOW": ("KNEW", "KNOWING", "KNOWS"),
    "LEAD": ("LED", "LEADING", "LEADS"),
    "MAKE": ("MADE", "MAKING", "MAKES"),
    "RUN": ("RAN", "RUNNING", "RUNS"),
    "SEND": ("SENT", "SENDING", "SENDS"),
    "SET": ("SET", "SETTING", "SETS"),
    "SHOW": ("SHOWED", "SHOWING", "SHOWS"),
    "TAKE": ("TOOK", "TAKING", "TAKES"),
    "TELL": ("TOLD", "TELLING", "TELLS"),
    "WRITE": ("WROTE", "WRITING", "WRITES"),
}

# Reverse lookup: any inflected form → base
_IRREGULAR_TO_BASE: dict[str, str] = {}
for _base, (_past, _ger, _third) in IRREGULARS.items():
    _IRREGULAR_TO_BASE[_base] = _base
    _IRREGULAR_TO_BASE[_past] = _base
    _IRREGULAR_TO_BASE[_ger] = _base
    _IRREGULAR_TO_BASE[_third] = _base

# Manual stem overrides for verbs whose inflected forms fool the rules.
# canonical_or_inflected → base form. Add entries here when the stemmer
# produces garbage for a specific word.
STEM_OVERRIDES: dict[str, str] = {
    # -ATE verbs: stem heuristic tries to add E after removing -ED/-S
    "REGULATE": "REGULATE",
    "REGULATES": "REGULATE",
    "REGULATED": "REGULATE",
    "REGULATING": "REGULATE",
    "OPERATE": "OPERATE",
    "OPERATES": "OPERATE",
    "OPERATED": "OPERATE",
    "OPERATING": "OPERATE",
    "CREATE": "CREATE",
    "CREATED": "CREATE",
    "CREATES": "CREATE",
    "CREATING": "CREATE",
    "MITIGATE": "MITIGATE",
    "MITIGATES": "MITIGATE",
    "MITIGATED": "MITIGATE",
    "MITIGATING": "MITIGATE",
    "COLLABORATE": "COLLABORATE",
    "COLLABORATES": "COLLABORATE",
    "COLLABORATED": "COLLABORATE",
    "COLLABORATING": "COLLABORATE",
    "INTEGRATE": "INTEGRATE",
    "INTEGRATES": "INTEGRATE",
    "INTEGRATED": "INTEGRATE",
    "INTEGRATING": "INTEGRATE",
    "EVALUATE": "EVALUATE",
    "EVALUATES": "EVALUATE",
    "EVALUATED": "EVALUATE",
    "EVALUATING": "EVALUATE",
    "AUTHORIZE": "AUTHORIZE",
    "AUTHORIZES": "AUTHORIZE",
    "AUTHORIZED": "AUTHORIZE",
    "AUTHORIZING": "AUTHORIZE",
    "ANNOUNCE": "ANNOUNCE",
    "ANNOUNCES": "ANNOUNCE",
    "ANNOUNCED": "ANNOUNCE",
    "ANNOUNCING": "ANNOUNCE",
    "PRODUCE": "PRODUCE",
    "PRODUCES": "PRODUCE",
    "PRODUCED": "PRODUCE",
    "PRODUCING": "PRODUCE",
    "ENFORCE": "ENFORCE",
    "ENFORCES": "ENFORCE",
    "ENFORCED": "ENFORCE",
    "ENFORCING": "ENFORCE",
    # Short verbs where -ED removal drops too much
    "FUND": "FUND",
    "FUNDED": "FUND",
    "FUNDS": "FUND",
    "FUNDING": "FUND",
    "HIRE": "HIRE",
    "HIRED": "HIRE",
    "HIRES": "HIRE",
    "HIRING": "HIRE",
    "LAUNCH": "LAUNCH",
    "LAUNCHED": "LAUNCH",
    "LAUNCHES": "LAUNCH",
    "LAUNCHING": "LAUNCH",
    "PUBLISH": "PUBLISH",
    "PUBLISHED": "PUBLISH",
    "PUBLISHES": "PUBLISH",
    "PUBLISHING": "PUBLISH",
    "RESEARCH": "RESEARCH",
    "RESEARCHED": "RESEARCH",
    "RESEARCHES": "RESEARCH",
    "RESEARCHING": "RESEARCH",
    # Verbs whose stemmer doubles consonants incorrectly
    "MONITOR": "MONITOR",
    "MONITORS": "MONITOR",
    "MONITORED": "MONITOR",
    "MONITORING": "MONITOR",
    "PARTNER": "PARTNER",
    "PARTNERED": "PARTNER",
    "PARTNERS": "PARTNER",
    "PARTNERING": "PARTNER",
    "TRANSFER": "TRANSFER",
    "TRANSFERRED": "TRANSFER",
    "TRANSFERS": "TRANSFER",
    "TRANSFERRING": "TRANSFER",
    "REPORT": "REPORT",
    "REPORTED": "REPORT",
    "REPORTS": "REPORT",
    "REPORTING": "REPORT",
    "GOVERN": "GOVERN",
    "GOVERNED": "GOVERN",
    "GOVERNS": "GOVERN",
    "GOVERNING": "GOVERN",
    "DETECT": "DETECT",
    "DETECTED": "DETECT",
    "DETECTS": "DETECT",
    "DETECTING": "DETECT",
    "RESPOND": "RESPOND",
    "RESPONDED": "RESPOND",
    "RESPONDS": "RESPOND",
    "RESPONDING": "RESPOND",
    "INSPECT": "INSPECT",
    "INSPECTED": "INSPECT",
    "INSPECTS": "INSPECT",
    "INSPECTING": "INSPECT",
    "CLASSIFY": "CLASSIFY",
    "CLASSIFIED": "CLASSIFY",
    "CLASSIFIES": "CLASSIFY",
    "CLASSIFYING": "CLASSIFY",
    "COMPLY": "COMPLY",
    "COMPLIED": "COMPLY",
    "COMPLIES": "COMPLY",
    "COMPLYING": "COMPLY",
    "ACQUIRE": "ACQUIRE",
    "ACQUIRED": "ACQUIRE",
    "ACQUIRES": "ACQUIRE",
    "ACQUIRING": "ACQUIRE",
    "UPDATE": "UPDATE",
    "UPDATED": "UPDATE",
    "UPDATES": "UPDATE",
    "UPDATING": "UPDATE",
    "MEASURE": "MEASURE",
    "MEASURED": "MEASURE",
    "MEASURES": "MEASURE",
    "MEASURING": "MEASURE",
    "REQUIRE": "REQUIRE",
    "REQUIRED": "REQUIRE",
    "REQUIRES": "REQUIRE",
    "REQUIRING": "REQUIRE",
    "TRAIN": "TRAIN",
    "TRAINED": "TRAIN",
    "TRAINS": "TRAIN",
    "TRAINING": "TRAIN",
}

# Prepositions that can trail a verb in compound relation names
PREPOSITIONS = {"WITH", "BY", "ON", "IN", "TO", "FOR", "FROM", "OF", "AT"}


def stem_verb(word: str) -> str:
    """Stem an inflected English verb back to its base/infinitive form.

    Examples:
        STORES → STORE, STORED → STORE, STORING → STORE
        REGULATES → REGULATE, REGULATED → REGULATE, REGULATING → REGULATE
        ANNOUNCES → ANNOUNCE, CLASSIFIED → CLASSIFY
        CREATED → CREATE, FUNDED → FUND, CAUSED → CAUSE
        MONITORS → MONITOR, MONITORED → MONITOR
    """
    # Check manual overrides first (handles words the rules get wrong)
    if word in STEM_OVERRIDES:
        return STEM_OVERRIDES[word]

    # Check irregular table
    if word in _IRREGULAR_TO_BASE:
        return _IRREGULAR_TO_BASE[word]

    # Gerund: -ING
    if word.endswith("ING") and len(word) > 4:
        stem = word[:-3]
        # STORING → STOR → STORE (doubled consonant removed)
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            return stem[:-1]
        # REGULATING → REGULAT → REGULATE (add back E)
        if stem.endswith(("AT", "AK", "AV", "AZ", "IC", "ID", "IL", "IN",
                          "IS", "IT", "IV", "OD", "OK", "OS", "OT", "OV",
                          "UD", "UK", "UR", "US", "UT")):
            return stem + "E"
        # LYING → LY → LIE
        if stem.endswith("Y") and len(stem) >= 2:
            return stem[:-1] + "IE"
        return stem

    # Past tense: -ED
    if word.endswith("ED") and len(word) > 3:
        stem = word[:-2]
        # CLASSIFIED → CLASSIFI → stem is CLASSIFI, want CLASSIFY
        if stem.endswith("I"):
            return stem[:-1] + "Y"
        # TRANSFERRED → TRANSFERR → TRANSFER (doubled consonant)
        if len(stem) >= 2 and stem[-1] == stem[-2]:
            return stem[:-1]
        # STORED → STOR → STORE, REGULATED → REGULAT → REGULATE
        # Check if adding E back makes more sense
        if stem[-1] not in "AEIOU" and not stem.endswith(("AIN", "EAR", "EAL",
                "EAT", "EED", "EEN", "EER", "EET", "OOL", "OON", "OOR",
                "OOT", "URN")):
            # Heuristic: if the stem ending doesn't look like a natural word
            # ending, try adding E. This handles STOR→STORE, CAUS→CAUSE, etc.
            # but NOT FUND→FUNDE (FUND is already fine).
            # We check: does the -ED form equal past_tense(stem+"E")?
            candidate = stem + "E"
            if _past_tense_regular(candidate) == word:
                return candidate
        return stem

    # Third person: -S or -ES
    if word.endswith("IES") and len(word) > 4:
        # COMPLIES → COMPLY, CLASSIFIES → CLASSIFY
        return word[:-3] + "Y"
    if word.endswith("SSES") or word.endswith("SHES") or word.endswith("CHES") or word.endswith("XES") or word.endswith("ZES"):
        # ADDRESSES → ADDRESS
        return word[:-2]
    if word.endswith("SES") and len(word) > 4:
        # ANNOUNCES → ANNOUNCE, PRODUCES → PRODUCE
        return word[:-1]
    if word.endswith("S") and not word.endswith("SS") and len(word) > 3:
        # MONITORS → MONITOR, AFFECTS → AFFECT, STORES → STORE
        return word[:-1]

    # Already base form
    return word


def _should_double_final(base: str) -> bool:
    """Whether the final consonant should double before -ED/-ING.

    English doubles the final consonant only when the last syllable is
    stressed AND ends in a single consonant preceded by a single vowel.
    For short (one-syllable) words this is straightforward. For longer
    words we use a conservative heuristic: only double for known short
    words, not for words like MONITOR, PARTNER, TRANSFER, REPORT, etc.
    """
    if len(base) < 3:
        return False
    if base[-1] in "AEIOUHWXY":
        return False
    if base[-2] not in "AEIOU":
        return False
    if base[-3] in "AEIOU":
        return False
    # Only double for short words (<=5 chars ≈ one syllable)
    # This prevents MONITOR→MONITORRED, PARTNER→PARTNERRED
    return len(base) <= 5


def _past_tense_regular(base: str) -> str:
    """Regular past tense from base form (no irregular lookup)."""
    if base.endswith("E"):
        return base + "D"
    if base.endswith("Y") and len(base) > 1 and base[-2] not in "AEIOU":
        return base[:-1] + "IED"
    if _should_double_final(base):
        return base + base[-1] + "ED"
    return base + "ED"


def inflect_base(base: str) -> dict[str, str]:
    """Generate all inflected forms from a base verb.

    Returns {form_name: inflected_word}.
    """
    forms: dict[str, str] = {"base": base}

    # Check irregulars
    if base in IRREGULARS:
        past, ger, third = IRREGULARS[base]
        forms["past"] = past
        forms["gerund"] = ger
        forms["third"] = third
        return forms

    # Past tense
    forms["past"] = _past_tense_regular(base)

    # Gerund (-ING)
    if base.endswith("IE"):
        forms["gerund"] = base[:-2] + "YING"
    elif base.endswith("E") and not base.endswith("EE"):
        forms["gerund"] = base[:-1] + "ING"
    elif _should_double_final(base):
        forms["gerund"] = base + base[-1] + "ING"
    else:
        forms["gerund"] = base + "ING"

    # Third person (-S/-ES)
    if base.endswith(("S", "SH", "CH", "X", "Z")):
        forms["third"] = base + "ES"
    elif base.endswith("Y") and len(base) > 1 and base[-2] not in "AEIOU":
        forms["third"] = base[:-1] + "IES"
    else:
        forms["third"] = base + "S"

    return forms


def split_relation(canonical: str) -> tuple[str, str]:
    """Split a relation name into (verb_part, preposition_suffix).

    COMPLIES_WITH → ("COMPLIES", "WITH")
    DETECTED_IN → ("DETECTED", "IN")
    DEPENDS_ON → ("DEPENDS", "ON")
    STORES → ("STORES", "")
    USES_TECH → ("USES", "TECH")  — TECH is not a preposition, stays as verb
    """
    parts = canonical.split("_")

    # Find the first preposition after at least one verb part
    for i in range(1, len(parts)):
        if parts[i] in PREPOSITIONS:
            verb = "_".join(parts[:i])
            suffix = "_".join(parts[i:])
            return verb, suffix

    return canonical, ""


def generate_variants(canonical: str) -> dict[str, str]:
    """Generate tense variants for a single canonical relation.

    Returns a dict of {variant_form: canonical} entries.
    """
    verb_part, suffix = split_relation(canonical)

    # For compound verbs like USES_TECH or USES_MODEL, stem the first word only
    # if the second word isn't a preposition
    if "_" in verb_part:
        # e.g., USES_TECH — stem USES to USE, keep TECH
        sub_parts = verb_part.split("_")
        base = stem_verb(sub_parts[0])
        # Generate forms for the first word, keep rest intact
        forms = inflect_base(base)
        rest = "_".join(sub_parts[1:])

        variants: dict[str, str] = {}
        for form_name, inflected in forms.items():
            full = f"{inflected}_{rest}"
            if suffix:
                full = f"{full}_{suffix}"
            if full != canonical:
                variants[full] = canonical
        # Also add _BY inversion for the whole thing
        if not suffix:
            variants[f"{canonical}_BY"] = canonical
        return variants

    # Simple verb (possibly with preposition suffix)
    base = stem_verb(verb_part)
    forms = inflect_base(base)

    variants = {}
    for form_name, inflected in forms.items():
        if suffix:
            full = f"{inflected}_{suffix}"
        else:
            full = inflected
        if full != canonical:
            variants[full] = canonical

    # _BY inversion (only for verbs without existing preposition suffix)
    if not suffix:
        variants[f"{canonical}_BY"] = canonical

    return variants


def load_domain_yaml(path: Path) -> dict:
    """Load and return parsed domain.yaml."""
    return yaml.safe_load(path.read_text())


def main():
    parser = argparse.ArgumentParser(
        description="Generate tense-variant normalization entries for a domain"
    )
    parser.add_argument("domain_yaml", type=Path, help="Path to domain.yaml")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write generated entries into domain.yaml (appends a generated block)",
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Show only entries not already in the normalization map",
    )
    args = parser.parse_args()

    if not args.domain_yaml.exists():
        print(f"Not found: {args.domain_yaml}")
        sys.exit(1)

    data = load_domain_yaml(args.domain_yaml)
    taxonomy = data.get("relation_taxonomy", {})
    canonical_list: list[str] = taxonomy.get("canonical", [])
    existing_norm: dict[str, str] = taxonomy.get("normalization", {}) or {}
    canonical_set = set(canonical_list)

    if not canonical_list:
        print("No canonical relations found in domain.yaml")
        sys.exit(1)

    print(f"Domain: {data.get('domain', {}).get('name', '?')}")
    print(f"Canonical relations: {len(canonical_list)}")
    print(f"Existing normalization entries: {len(existing_norm)}")
    print()

    # Generate all variants
    all_variants: dict[str, str] = {}
    skipped: list[tuple[str, str, str]] = []

    for canon in canonical_list:
        variants = generate_variants(canon)
        for variant, target in variants.items():
            # Skip if variant is itself a canonical type (different meaning)
            if variant in canonical_set:
                skipped.append((variant, target, "is a canonical type"))
                continue

            # Skip if already mapped to something different
            if variant in existing_norm and existing_norm[variant] != target:
                skipped.append(
                    (variant, target, f"already maps to {existing_norm[variant]}")
                )
                continue

            # Skip if already in normalization with same target
            if args.new_only and variant in existing_norm:
                continue

            all_variants[variant] = target

    # Report
    new_variants = {
        k: v for k, v in all_variants.items() if k not in existing_norm
    }
    existing_variants = {
        k: v for k, v in all_variants.items() if k in existing_norm
    }

    if new_variants:
        print(f"NEW entries to add ({len(new_variants)}):")
        by_target: dict[str, list[str]] = {}
        for var, tgt in sorted(new_variants.items()):
            by_target.setdefault(tgt, []).append(var)
        for tgt in sorted(by_target):
            for var in by_target[tgt]:
                print(f"    {var}: {tgt}")
        print()

    if existing_variants and not args.new_only:
        print(f"Already covered ({len(existing_variants)}):")
        for var, tgt in sorted(existing_variants.items()):
            print(f"    {var}: {tgt}  (exists)")
        print()

    if skipped:
        print(f"Skipped ({len(skipped)}):")
        for var, tgt, reason in sorted(skipped):
            print(f"    {var} → {tgt}: {reason}")
        print()

    total_after = len(existing_norm) + len(new_variants)
    print(f"Summary: {len(existing_norm)} existing + {len(new_variants)} new = {total_after} total")

    if args.apply and new_variants:
        raw_text = args.domain_yaml.read_text()

        lines = [
            "",
            "    # --- Auto-generated tense variants (generate_normalization.py) ---",
            "    # Review these entries. Remove any that collide with domain-specific",
            "    # meanings (e.g., if CONTAINED means something different from CONTAINS).",
        ]
        by_target = {}
        for var, tgt in sorted(new_variants.items()):
            by_target.setdefault(tgt, []).append(var)
        for tgt in sorted(by_target):
            for var in by_target[tgt]:
                lines.append(f"    {var}: {tgt}")

        block = "\n".join(lines) + "\n"

        yaml_lines = raw_text.split("\n")
        insert_idx = None
        in_normalization = False
        for i, line in enumerate(yaml_lines):
            stripped = line.strip()
            if stripped.startswith("normalization:"):
                in_normalization = True
                continue
            if in_normalization:
                if re.match(r"^    \S+.*: \S+", line):
                    insert_idx = i
                elif stripped and not stripped.startswith("#") and not line.startswith("    "):
                    break

        if insert_idx is not None:
            yaml_lines.insert(insert_idx + 1, block.rstrip())
            args.domain_yaml.write_text("\n".join(yaml_lines))
            print(f"\nWrote {len(new_variants)} entries to {args.domain_yaml}")
            print("Review the generated block and remove any domain-inappropriate entries.")
        else:
            print("\nCould not find insertion point in YAML. Add manually:")
            print(block)


if __name__ == "__main__":
    main()
