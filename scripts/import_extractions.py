"""Import validated extraction JSON files into the database.

Resolves entities via EntityResolver, inserts relations and evidence,
and updates document status to 'extracted'.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add src/ to import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from db import init_db, insert_relation, insert_evidence
from extract import EXTRACTOR_VERSION
from resolve import EntityResolver
from schema import validate_extraction, ValidationError


def import_extractions(
    db_path: Path,
    extractions_dir: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    """Import extraction JSON files into the database.

    Args:
        db_path: Path to SQLite database
        extractions_dir: Directory containing extraction JSON files
        dry_run: If True, validate only without writing to DB

    Returns:
        Statistics dict with counts
    """
    conn = init_db(db_path)
    resolver = EntityResolver(conn, threshold=0.85)

    stats = {
        "files_processed": 0,
        "entities_total": 0,
        "entities_new": 0,
        "entities_resolved": 0,
        "relations": 0,
        "evidence_records": 0,
        "errors": 0,
    }

    json_files = sorted(extractions_dir.glob("*.json"))
    if not json_files:
        print(f"No extraction files found in {extractions_dir}")
        conn.close()
        return stats

    for json_file in json_files:
        print(f"Processing {json_file.name}...")

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                extraction = json.load(f)

            # Validate against schema
            validate_extraction(extraction)
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"  ERROR: {json_file.name}: {e}")
            stats["errors"] += 1
            continue

        doc_id = extraction["docId"]

        if dry_run:
            stats["files_processed"] += 1
            continue

        # Look up document's published date for entity timestamps
        cursor = conn.execute(
            "SELECT published_at FROM documents WHERE doc_id = ?",
            (doc_id,)
        )
        row = cursor.fetchone()
        doc_published = row[0] if row else None

        # Resolve entities — get name-to-ID mapping
        # Track which are new vs resolved to existing
        entities_before = set()
        cursor = conn.execute("SELECT entity_id FROM entities")
        entities_before = {row[0] for row in cursor.fetchall()}

        name_to_id = resolver.resolve_extraction(extraction, observed_date=doc_published)

        entities_after = set()
        cursor = conn.execute("SELECT entity_id FROM entities")
        entities_after = {row[0] for row in cursor.fetchall()}

        new_entities = entities_after - entities_before
        stats["entities_total"] += len(name_to_id)
        stats["entities_new"] += len(new_entities)
        stats["entities_resolved"] += len(name_to_id) - len(new_entities)

        # Insert relations
        for rel in extraction.get("relations", []):
            source_id = name_to_id.get(rel["source"])
            target_id = name_to_id.get(rel["target"])

            if not source_id or not target_id:
                print(
                    f"  WARNING: Skipping relation {rel['source']} → {rel['target']}: "
                    f"entity not resolved"
                )
                continue

            time_obj = rel.get("time", {})

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

            # Insert evidence for this relation
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
                stats["evidence_records"] += 1

        # Update document status
        conn.execute(
            "UPDATE documents SET status = 'extracted' WHERE doc_id = ?",
            (doc_id,),
        )
        conn.commit()

        stats["files_processed"] += 1
        print(f"  Imported: {len(name_to_id)} entities, "
              f"{sum(1 for r in extraction.get('relations', []) if name_to_id.get(r.get('source')) and name_to_id.get(r.get('target')))} relations")

    conn.close()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import extraction JSON files into the database."
    )
    parser.add_argument(
        "--db", default="data/db/predictor.db",
        help="Path to SQLite database (default: data/db/predictor.db)",
    )
    parser.add_argument(
        "--extractions-dir", default="data/extractions",
        help="Directory containing extraction JSON files (default: data/extractions)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate only, don't write to DB",
    )
    args = parser.parse_args()

    stats = import_extractions(
        db_path=Path(args.db),
        extractions_dir=Path(args.extractions_dir),
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(f"\n[DRY RUN] Validated {stats['files_processed']} extraction files (no DB changes)")
    else:
        print(f"\nImported {stats['files_processed']} extraction files:")
        print(f"  - {stats['entities_total']} entities "
              f"({stats['entities_new']} new, {stats['entities_resolved']} resolved to existing)")
        print(f"  - {stats['relations']} relations")
        print(f"  - {stats['evidence_records']} evidence records")

    if stats["errors"] > 0:
        print(f"  - {stats['errors']} files had errors")

    return 1 if stats["errors"] > 0 and stats["files_processed"] == 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
