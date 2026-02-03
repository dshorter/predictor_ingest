#!/usr/bin/env python3
"""
Extraction Import Script

Imports manual extraction JSON files into the database.
Validates against schema, resolves entities to canonical IDs,
and inserts relations and evidence.
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from db import init_db, insert_relation, insert_evidence
from extract import import_manual_extraction, EXTRACTOR_VERSION
from resolve import EntityResolver


def import_extraction(conn, resolver, extraction_file, extraction, dry_run=False):
    """
    Import a single extraction file into the database.

    Args:
        conn: Database connection
        resolver: EntityResolver instance
        extraction_file: Path to extraction file (for logging)
        extraction: Parsed extraction dict
        dry_run: If True, don't write to database

    Returns:
        Dict with import statistics
    """
    doc_id = extraction["docId"]
    stats = {
        "entities_new": 0,
        "entities_matched": 0,
        "relations": 0,
        "evidence": 0,
        "skipped_relations": 0
    }

    # Step 1: Resolve entities → get name-to-ID mapping
    # This calls resolver.resolve_or_create() for each entity
    name_to_id = resolver.resolve_extraction(extraction)

    # Count new vs matched entities
    for entity in extraction.get("entities", []):
        entity_name = entity["name"]
        if entity_name in name_to_id:
            # Check if it was newly created or matched existing
            # (resolver tracks this internally, but for now we estimate)
            stats["entities_new"] += 1  # Simplified for V1

    # Step 2: Insert relations using resolved IDs
    for rel in extraction.get("relations", []):
        source_name = rel["source"]
        target_name = rel["target"]

        source_id = name_to_id.get(source_name)
        target_id = name_to_id.get(target_name)

        if not source_id or not target_id:
            print(f"  WARNING: Skipping relation {source_name} → {target_name}: "
                  f"entity not resolved", file=sys.stderr)
            stats["skipped_relations"] += 1
            continue

        if dry_run:
            stats["relations"] += 1
            stats["evidence"] += len(rel.get("evidence", []))
            continue

        # Extract optional time fields
        time_obj = rel.get("time", {})

        # Insert relation
        relation_id = insert_relation(
            conn,
            source_id=source_id,
            rel=rel["rel"],
            target_id=target_id,
            kind=rel["kind"],
            confidence=rel["confidence"],
            doc_id=doc_id,
            extractor_version=extraction.get("extractorVersion", EXTRACTOR_VERSION),
            verb_raw=rel.get("verbRaw"),
            polarity=rel.get("polarity"),
            modality=rel.get("modality"),
            time_text=time_obj.get("text"),
            time_start=time_obj.get("start"),
            time_end=time_obj.get("end"),
        )

        stats["relations"] += 1

        # Step 3: Insert evidence for this relation
        for ev in rel.get("evidence", []):
            char_span = ev.get("charSpan", {})

            insert_evidence(
                conn,
                relation_id=relation_id,
                doc_id=ev["docId"],
                url=ev["url"],
                published=ev.get("published"),
                snippet=ev["snippet"],
                char_start=char_span.get("start"),
                char_end=char_span.get("end"),
            )

            stats["evidence"] += 1

    # Step 4: Update document status
    if not dry_run:
        conn.execute(
            "UPDATE documents SET status = 'extracted' WHERE doc_id = ?",
            (doc_id,)
        )
        conn.commit()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Import extraction JSON files into the database"
    )
    parser.add_argument(
        '--db',
        default='data/db/predictor.db',
        help='Database path (default: data/db/predictor.db)'
    )
    parser.add_argument(
        '--extractions-dir',
        default='data/extractions',
        help='Directory containing extraction JSON files (default: data/extractions)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate only, don\'t write to database'
    )

    args = parser.parse_args()

    # Resolve paths
    repo_root = Path(__file__).parent.parent
    db_path = repo_root / args.db
    extractions_dir = repo_root / args.extractions_dir

    # Validate database
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        print("Run 'make init-db' first.", file=sys.stderr)
        sys.exit(1)

    # Validate extractions directory
    if not extractions_dir.exists():
        print(f"ERROR: Extractions directory not found at {extractions_dir}", file=sys.stderr)
        print("Create some extraction JSON files first.", file=sys.stderr)
        sys.exit(1)

    # Find extraction files
    extraction_files = sorted(extractions_dir.glob("*.json"))

    if not extraction_files:
        print(f"No extraction files found in {extractions_dir}")
        sys.exit(0)

    print(f"Importing extractions from {extractions_dir}...\n")

    # Connect to database
    conn = init_db(str(db_path))

    try:
        # Create resolver
        resolver = EntityResolver(conn, threshold=0.85)

        # Aggregate stats
        total_stats = {
            "files": 0,
            "entities_new": 0,
            "entities_matched": 0,
            "relations": 0,
            "evidence": 0,
            "skipped_relations": 0
        }

        # Process each extraction file
        for extraction_file in extraction_files:
            try:
                # Step 1: Validate and load extraction
                extraction = import_manual_extraction(extraction_file, extractions_dir)

                print(f"Processing {extraction_file.name}...")

                # Step 2: Import into database
                stats = import_extraction(conn, resolver, extraction_file, extraction, args.dry_run)

                # Print stats
                print(f"  - {stats['entities_new']} entities")
                print(f"  - {stats['relations']} relations")
                print(f"  - {stats['evidence']} evidence records")

                if stats['skipped_relations'] > 0:
                    print(f"  - {stats['skipped_relations']} relations skipped (entities not resolved)")

                # Aggregate
                total_stats["files"] += 1
                total_stats["entities_new"] += stats["entities_new"]
                total_stats["entities_matched"] += stats["entities_matched"]
                total_stats["relations"] += stats["relations"]
                total_stats["evidence"] += stats["evidence"]
                total_stats["skipped_relations"] += stats["skipped_relations"]

                print()

            except Exception as e:
                print(f"ERROR processing {extraction_file.name}: {e}", file=sys.stderr)
                print()
                continue

        # Print summary
        if args.dry_run:
            print(f"[DRY RUN] Validated {total_stats['files']} extraction files (no DB changes)")
        else:
            print(f"Imported {total_stats['files']} extraction files:")
            print(f"  - {total_stats['entities_new']} entities")
            print(f"  - {total_stats['relations']} relations")
            print(f"  - {total_stats['evidence']} evidence records")
            print(f"  - {total_stats['files']} documents marked as 'extracted'")

            if total_stats['skipped_relations'] > 0:
                print(f"\nWARNING: {total_stats['skipped_relations']} relations skipped due to unresolved entities")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
