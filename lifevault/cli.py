import argparse
import sys
from .core.db import ManifestDatabase
from .engine.deduplicator import DeduplicationEngine
from .engine.refiner import RefinementEngine
from .engine.syncer import IncrementalSyncEngine
from .recovery.auditor import VaultAuditor
from .recovery.rollback import RollbackEngine

def main():
    parser = argparse.ArgumentParser(
        prog="lifevault",
        description="LifeVault: Sovereign Personal Memory Engine & Multi-Drive Disaster-Proof Backup Tool"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Dedup command
    dedup_parser = subparsers.add_parser("dedup", help="Analyze and quarantine exact bit-for-bit duplicates")
    dedup_parser.add_argument("--db", required=True, help="Path to manifest database")

    # 2. Refine command
    refine_parser = subparsers.add_parser("refine", help="Organize primary files chronologically into YYYY/YYYY-MM")
    refine_parser.add_argument("--db", required=True, help="Path to manifest database")
    refine_parser.add_argument("--target", required=True, help="Target root directory for refined media")
    refine_parser.add_argument("--quarantine", required=True, help="Directory for quarantined duplicates")
    refine_parser.add_argument("--dry-run", action="store_true", help="Simulate without moving files")

    # 3. Sync command
    sync_parser = subparsers.add_parser("sync", help="Incremental backup sync from fast staging to travel drive")
    sync_parser.add_argument("--source", required=True, help="Source staging directory")
    sync_parser.add_argument("--dest", required=True, help="Destination backup directory")
    sync_parser.add_argument("--audit-db", default="sync_audit.db", help="Path to SQLite sync audit log")

    # 4. Audit command
    audit_parser = subparsers.add_parser("audit", help="Verify 100% preservation between source and vault")
    audit_parser.add_argument("--source", required=True, help="Source root directory")
    audit_parser.add_argument("--target", required=True, help="Target vault root directory")

    # 5. Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Atomic rollback of refined files to original locations")
    rollback_parser.add_argument("--db", required=True, help="Path to manifest database")

    args = parser.parse_args()

    if args.command == "dedup":
        db = ManifestDatabase(args.db)
        engine = DeduplicationEngine(db.get_connection())
        groups, dupes, saved = engine.identify_exact_duplicates()
        print(f"Deduplication Analysis Complete: {groups} duplicate groups, {dupes} duplicate files identified ({saved / (1024**3):.2f} GB).")

    elif args.command == "refine":
        db = ManifestDatabase(args.db)
        engine = RefinementEngine(db.get_connection(), args.target, args.quarantine)
        refined, quar = engine.execute(dry_run=args.dry_run)
        print(f"Refinement Complete: {refined} primary files organized, {quar} duplicates quarantined.")

    elif args.command == "sync":
        engine = IncrementalSyncEngine(args.source, args.dest, args.audit_db)
        res = engine.sync()
        print(f"Sync Complete: {res['files_copied']} files transferred ({res['bytes_copied']/(1024**3):.2f} GB). Status: {res['status']}")

    elif args.command == "audit":
        res = VaultAuditor.audit_directories(args.source, args.target)
        print(f"Audit Complete: Source has {res['source_total_files']} files, Target has {res['target_total_files']} files.")
        print(f"Missing Files: {res['missing_count']} | Size Mismatches: {res['mismatch_count']}")

    elif args.command == "rollback":
        engine = RollbackEngine(args.db)
        res = engine.rollback()
        print(f"Rollback Complete: {res['restored']} files restored to original locations (Failed: {res['failed']}).")

if __name__ == "__main__":
    main()
