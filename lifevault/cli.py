import os
from typing import Optional
import typer
from rich.console import Console

from .core.db import ManifestDatabase
from .core.parquet_store import ParquetStore
from .engine.deduplicator import DeduplicationEngine
from .engine.syncer import IncrementalSyncEngine
from .intelligence.near_dup import NearDuplicateMatcher
from .intelligence.geo_interpolator import GeoInterpolator
from .recovery.auditor import VaultAuditor
from .recovery.rollback import RollbackEngine

from .connectors.samsung_health import SamsungHealthConnector
from .connectors.google_takeout import GoogleTakeoutConnector
from .connectors.dcim import DcimConnector
from .connectors.whatsapp import WhatsAppConnector
from .connectors.audio_calls import AudioCallsConnector
from .connectors.snapchat import SnapchatConnector
from .connectors.email_mbox import EmailConnector

app = typer.Typer(
    name="lifevault",
    help="LifeVault v2.0: Sovereign Personal Data Lakehouse & Cryptographic Archivist"
)
console = Console()

@app.command()
def ingest(
    connector: str = typer.Argument(..., help="Connector: shealth, takeout, dcim, whatsapp, calls, snapchat, email"),
    path: str = typer.Argument(..., help="Source directory or file to ingest"),
    db: str = typer.Option("manifest.db", "--db", help="SQLite manifest path"),
    telemetry_root: str = typer.Option("_Telemetry", "--telemetry-root", help="Parquet telemetry directory")
):
    m_db = ManifestDatabase(db)
    store = ParquetStore(telemetry_root)
    conn_map = {
        "shealth": SamsungHealthConnector(m_db, store),
        "takeout": GoogleTakeoutConnector(m_db, store),
        "dcim": DcimConnector(m_db, store),
        "whatsapp": WhatsAppConnector(m_db, store),
        "calls": AudioCallsConnector(m_db, store),
        "snapchat": SnapchatConnector(m_db, store),
        "email": EmailConnector(m_db, store)
    }
    c = conn_map.get(connector.lower())
    if not c:
        console.print(f"[red]Unknown connector: {connector}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[cyan]Ingesting {connector} from {path}...[/cyan]")
    res = c.ingest(path)
    console.print(f"[green]Ingest complete:[/green] {res}")

@app.command()
def link(
    db: str = typer.Option("manifest.db", "--db", help="SQLite manifest path"),
    max_dist: int = typer.Option(8, "--max-dist", help="Maximum hamming distance")
):
    m_db = ManifestDatabase(db)
    matcher = NearDuplicateMatcher(m_db)
    console.print(f"[cyan]Scanning for near-duplicate photos (pHash distance <= {max_dist})...[/cyan]")
    cnt = matcher.link_perceptual_duplicates(max_dist=max_dist)
    console.print(f"[green]Linked {cnt} near-duplicate edges in item_links table.[/green]")

@app.command()
def interpolate(
    db: str = typer.Option("manifest.db", "--db", help="SQLite manifest path"),
    telemetry_root: str = typer.Option("_Telemetry", "--telemetry-root", help="Parquet telemetry directory"),
    max_gap: float = typer.Option(600.0, "--max-gap", help="Max gap in seconds")
):
    m_db = ManifestDatabase(db)
    store = ParquetStore(telemetry_root)
    interp = GeoInterpolator(m_db, store)
    console.print("[cyan]Interpolating GPS for untagged photos from wearable trackpoints...[/cyan]")
    updated = interp.interpolate_photos(max_gap_sec=max_gap)
    console.print(f"[green]Interpolated GPS for {updated} photos/videos.[/green]")

@app.command()
def dedup(
    db: str = typer.Option("manifest.db", "--db", help="SQLite manifest path")
):
    m_db = ManifestDatabase(db)
    engine = DeduplicationEngine(m_db.get_connection())
    console.print("[cyan]Analyzing exact bit-for-bit duplicates...[/cyan]")
    groups, dupes, saved = engine.identify_exact_duplicates()
    console.print(f"[green]Deduplication Complete:[/green] {groups} duplicate groups, {dupes} duplicates ({saved / (1024**3):.2f} GB).")

@app.command()
def sync(
    source: str = typer.Option(..., "--source", help="Source staging directory"),
    dest: str = typer.Option(..., "--dest", help="Destination backup directory"),
    audit_db: str = typer.Option("sync_audit.db", "--audit-db", help="Path to SQLite sync audit log")
):
    engine = IncrementalSyncEngine(source, dest, audit_db)
    console.print(f"[cyan]Syncing {source} -> {dest}...[/cyan]")
    res = engine.sync()
    console.print(f"[green]Sync Complete:[/green] {res['files_copied']} files transferred ({res['bytes_copied']/(1024**3):.2f} GB). Status: {res['status']}")

@app.command()
def audit(
    source: str = typer.Option(..., "--source", help="Source root directory"),
    target: str = typer.Option(..., "--target", help="Target vault root directory")
):
    console.print(f"[cyan]Forensic cross-drive audit: {source} vs {target}...[/cyan]")
    res = VaultAuditor.audit_directories(source, target)
    console.print(f"[green]Audit Complete:[/green] Source: {res['source_total_files']} files, Target: {res['target_total_files']} files.")
    console.print(f"Missing: {res['missing_count']} | Size Mismatches: {res['mismatch_count']}")

@app.command()
def rollback(
    db: str = typer.Option("manifest.db", "--db", help="SQLite manifest path")
):
    engine = RollbackEngine(db)
    console.print(f"[yellow]Restoring files from manifest {db}...[/yellow]")
    res = engine.rollback()
    console.print(f"[green]Rollback Complete:[/green] {res['restored']} restored, {res['failed']} failed.")

def main():
    app()

if __name__ == "__main__":
    main()
