# 🏛️ LifeVault: Sovereign Personal Memory & Backup Engine
> **An enterprise-grade, zero-loss multi-drive storage architecture, cryptographic verification pipeline, and personal memory ground-truth engine for humans and Digital Twins.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-brightgreen.svg)](https://python.org)
[![Storage Integrity](https://img.shields.io/badge/Data%20Integrity-SHA--256%20Verified-success.svg)]()

---

## 🌌 Overview

Over a lifetime, every person accumulates hundreds of thousands of digital memories: smartphone camera rolls, DSLR RAW images, call recordings, voice notes, childhood family albums, scanned vintage documents, and university archives. 

Today, this data is fractured across old laptops, failing external HDDs, and proprietary cloud silos (Google Photos, iCloud). Most people live in constant fear of drive corruption, accidental deletion, or cloud lockout.

**LifeVault** provides an open-source, mathematically proven framework to:
1. **Consolidate and organize** fragmented media into an immutable chronological catalog (`YYYY/YYYY-MM`).
2. **Eliminate duplicates with zero data loss** by safely segregating them into a bit-for-bit quarantine archive rather than destructive deletion.
3. **Enforce a 4-Tier Zero-Loss Redundancy Model** (NVMe Staging -> Master Cold Vault -> Offline Heritage Vault -> Mobile Travel Backup).
4. **Prepare sovereign ground-truth context** for the emerging era of **Personal AI & Digital Twins**.

---

## 🏗️ 4-Tier Multi-Drive Storage Topology

```mermaid
flowchart TD
    subgraph Tier1 ["⚡ Tier 1: Fast Ingest & Cloud Base"]
        Dev["📱 Phones, DSLRs & Camera SDs"] -->|High Speed| NVMe["⚡ Fast NVMe SSD (D:\DCIM)<br/><i>Primary Ingestion Buffer</i>"]
        NVMe -->|Direct Cloud Sync| Cloud["☁️ Google Photos / Cloud"]
    end

    subgraph ColdVaults ["🏛️ Tier 2 & 3: Master Cold Vaults (Permanent Offline Base)"]
        NVMe -->|Batch Process & Audit| Engine["⚙️ LifeVault Engine"]
        Engine -->|Master Copy 1 (100% Everything)| Master["🏛️ 4TB+ Master Cold Vault<br/><i>Complete Uncut Archive</i>"]
        Engine -->|Dedicated Copy 2 (Priceless Vault)| Heritage["🏠 Dedicated Offline Heritage Vault<br/><i>Childhood Memories + Voice Recordings</i>"]
    end

    subgraph Tier4 ["🎒 Tier 4: Mobile Travel Drive"]
        NVMe -->|1-Click Incremental Sync| Travel["🎒 1TB Mobile Travel Drive<br/><i>On-The-Road Working Backup</i>"]
    end
```

---

## 🚀 Quickstart & Installation

### Installation
Clone the repository and install locally:
```bash
git clone https://github.com/kartabyakrishna/LifeVault.git
cd LifeVault
pip install -e .
```

### 1. Deduplicate & Quarantine Identical Copies
Identify exact bit-for-bit duplicate copies using streaming SHA-256 hashes:
```bash
lifevault dedup --db manifest.db
```

### 2. Refine Chronologically
Classify primary media into clean `YYYY/YYYY-MM` hierarchies and isolate duplicates into quarantine:
```bash
lifevault refine --db manifest.db --target "/Volumes/Vault/Refine" --quarantine "/Volumes/Vault/Quarantine"
```

### 3. Incremental 1-Click Sync to Travel Drive
Sync newly staged photos from your fast internal drive to your portable travel backup:
```bash
lifevault sync --source "D:/DCIM" --dest "G:/DCIM" --audit-db "G:/DCIM/sync_audit.db"
```

### 4. Forensic Cross-Drive Audit
Verify that 100% of files from your source drive exist on your vault drive:
```bash
lifevault audit --source "E:/SourceDrive" --target "F:/Vault"
```

### 5. Atomic Rollback (Zero-Risk Guarantee)
Restore all moved and quarantined files back to their original locations in case of any issues:
```bash
lifevault rollback --db manifest.db
```

---

## 🛡️ Core Safety Invariants

- **Absolute Zero Deletion**: No file is ever deleted automatically. Duplicates are placed in a mirror quarantine hierarchy.
- **ACID SQLite Manifest**: Every file path, size, and hash is committed to an SQLite WAL database before filesystem operations occur.
- **Deep Directory Preservation**: Non-media archives (voice notes, call logs, documents) maintain their exact original subfolder structure down to all levels.
- **Cloud Independence**: Cloud sync operates strictly from fast local SSD storage, never bottlenecking slow external mechanical hard drives.

---

## 📄 License
Released under the [MIT License](LICENSE). Built for humans and digital twins everywhere.
