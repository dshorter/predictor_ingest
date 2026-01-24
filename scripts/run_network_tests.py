#!/usr/bin/env python3
"""Run network-dependent tests that require local execution.

These tests require:
- Network access to external RSS feeds
- feedparser and requests packages installed

Usage:
    python scripts/run_network_tests.py
    python scripts/run_network_tests.py -v          # Verbose
    python scripts/run_network_tests.py --quick     # Just feed parsing, no full ingestion
"""

import subprocess
import sys
from pathlib import Path


def main():
    repo_root = Path(__file__).parent.parent

    # Build pytest command
    cmd = [
        sys.executable, "-m", "pytest",
        str(repo_root / "tests"),
        "-m", "network",
        "--tb=short",
    ]

    # Pass through any additional arguments
    if "-v" in sys.argv or "--verbose" in sys.argv:
        cmd.append("-v")

    if "--quick" in sys.argv:
        # Only run the fast feed parsing tests, skip full ingestion
        cmd.extend(["-k", "fetch_arxiv or fetch_huggingface or fetch_openai"])

    # Set PYTHONPATH
    env = {"PYTHONPATH": str(repo_root / "src")}

    print("=" * 60)
    print("Running network-dependent tests")
    print("These require internet access to RSS feeds")
    print("=" * 60)
    print(f"\nCommand: {' '.join(cmd)}\n")

    # Run tests
    result = subprocess.run(cmd, cwd=repo_root, env={**dict(__import__('os').environ), **env})

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
