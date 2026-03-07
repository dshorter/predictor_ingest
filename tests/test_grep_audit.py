"""Grep-audit: ensure framework code has zero AI-domain-specific strings.

Framework modules (src/extract, src/trend, src/schema, src/domain, src/graph,
src/resolve) must not contain hardcoded AI-domain values. All domain-specific
content should come from the active domain profile.

This test catches regressions where someone re-introduces a hardcoded
domain value into framework code.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Framework source directories (domain-independent code)
_SRC = Path(__file__).resolve().parents[1] / "src"
_FRAMEWORK_DIRS = [
    _SRC / "extract",
    _SRC / "trend",
    _SRC / "schema",
    _SRC / "domain",
    _SRC / "graph",
    _SRC / "resolve",
]

# Patterns that indicate AI-domain-specific hardcoding.
# Each tuple: (pattern_regex, description, allowed_contexts)
# allowed_contexts: list of regex patterns for lines that are OK
_FORBIDDEN_PATTERNS = [
    (
        r"""['"]MENTIONS['"]""",
        "hardcoded MENTIONS relation (use _BASE_RELATION or profile)",
        [
            r"#",           # comments
            r"docstring",   # in docstrings
            r"base_relation",  # referencing config key
            r"test",        # test references
        ],
    ),
    (
        r"""['"]CITES['"]""",
        "hardcoded CITES relation",
        [r"#"],
    ),
    (
        r"""['"]ANNOUNCES['"]""",
        "hardcoded ANNOUNCES relation",
        [r"#"],
    ),
    (
        r"entity_types\s*=\s*\[",
        "hardcoded entity_types list (should load from profile)",
        [r"#", r"profile", r"_profile"],
    ),
    (
        r"""frozenset\(\s*\[\s*['"]Org['"]""",
        "hardcoded entity type frozenset",
        [],
    ),
    (
        r"0\.15\s*\*.*0\.15\s*\*.*0\.10\s*\*",
        "hardcoded scoring weights pattern",
        [],
    ),
    (
        r"0\.4\s*\*\s*velocity.*0\.3\s*\*\s*novelty",
        "hardcoded trend weights pattern",
        [],
    ),
]


def _collect_python_files() -> list[Path]:
    """Collect all .py files in framework directories."""
    files = []
    for d in _FRAMEWORK_DIRS:
        if d.is_dir():
            files.extend(d.rglob("*.py"))
    return sorted(files)


class TestGrepAudit:
    """Verify no AI-domain-specific strings leak into framework code."""

    def test_no_hardcoded_relation_strings(self):
        """Framework code must not contain hardcoded relation type strings."""
        violations = []
        for py_file in _collect_python_files():
            content = py_file.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                # Skip comments and docstrings
                if stripped.startswith("#"):
                    continue
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    continue

                for pattern, desc, allowed in _FORBIDDEN_PATTERNS[:3]:
                    if re.search(pattern, line):
                        # Check if line matches any allowed context
                        if any(re.search(ctx, line, re.IGNORECASE) for ctx in allowed):
                            continue
                        rel_path = py_file.relative_to(_SRC.parent)
                        violations.append(f"  {rel_path}:{line_no}: {desc}\n    {stripped}")

        assert not violations, (
            f"Found {len(violations)} hardcoded relation string(s) in framework code:\n"
            + "\n".join(violations)
        )

    def test_no_hardcoded_entity_type_lists(self):
        """Framework code must not define inline entity type lists."""
        violations = []
        for py_file in _collect_python_files():
            content = py_file.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue

                for pattern, desc, allowed in _FORBIDDEN_PATTERNS[3:5]:
                    if re.search(pattern, line):
                        if any(re.search(ctx, line, re.IGNORECASE) for ctx in allowed):
                            continue
                        rel_path = py_file.relative_to(_SRC.parent)
                        violations.append(f"  {rel_path}:{line_no}: {desc}\n    {stripped}")

        assert not violations, (
            f"Found {len(violations)} hardcoded entity type list(s) in framework code:\n"
            + "\n".join(violations)
        )

    def test_no_hardcoded_weight_patterns(self):
        """Framework code must not have hardcoded scoring/trend weight patterns."""
        violations = []
        for py_file in _collect_python_files():
            content = py_file.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue

                for pattern, desc, allowed in _FORBIDDEN_PATTERNS[5:]:
                    if re.search(pattern, line):
                        if any(re.search(ctx, line, re.IGNORECASE) for ctx in allowed):
                            continue
                        rel_path = py_file.relative_to(_SRC.parent)
                        violations.append(f"  {rel_path}:{line_no}: {desc}\n    {stripped}")

        assert not violations, (
            f"Found {len(violations)} hardcoded weight pattern(s) in framework code:\n"
            + "\n".join(violations)
        )

    def test_framework_dirs_exist(self):
        """At least some framework directories should exist."""
        existing = [d for d in _FRAMEWORK_DIRS if d.is_dir()]
        assert len(existing) >= 3, (
            f"Expected at least 3 framework dirs, found {len(existing)}: "
            f"{[d.name for d in existing]}"
        )
