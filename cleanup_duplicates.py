#!/usr/bin/env python3
"""cleanup_duplicates.py
─────────────────────────
Remove duplicate rows from `disponibilidades`, keeping only the record with
the **lowest id** for each unique (service_id, data, horario) combination.

Run BEFORE migrate_db.py when you see:
  "Could not create index (duplicate data exists?)"

Usage:
    python cleanup_duplicates.py
"""
import os
import sys
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "instance", "medmarket.db")

if not os.path.exists(DB_PATH):
    print(f"ERROR: Database not found at {DB_PATH}")
    sys.exit(1)

print(f"Database: {DB_PATH}")

with sqlite3.connect(DB_PATH) as conn:
    conn.row_factory = sqlite3.Row

    # ── Find duplicate groups ────────────────────────────────────────────────
    dupes = conn.execute("""
        SELECT service_id,
               data,
               horario,
               COUNT(*)   AS cnt,
               MIN(id)    AS keep_id
        FROM   disponibilidades
        GROUP  BY service_id, data, horario
        HAVING COUNT(*) > 1
    """).fetchall()

    if not dupes:
        print("✓ No duplicates found. Database is clean.")
        sys.exit(0)

    print(f"\nFound {len(dupes)} duplicate slot(s). Removing extras...\n")

    total_removed = 0
    for row in dupes:
        result = conn.execute(
            """
            DELETE FROM disponibilidades
            WHERE  service_id = ?
              AND  data       = ?
              AND  horario    = ?
              AND  id        != ?
            """,
            (row["service_id"], row["data"], row["horario"], row["keep_id"]),
        )
        n = result.rowcount
        total_removed += n
        print(
            f"  · service_id={row['service_id']}  date={row['data']}"
            f"  time={row['horario']}  "
            f"kept id={row['keep_id']}, removed {n} duplicate(s)"
        )

    conn.commit()
    print(f"\n✓ Done. Removed {total_removed} duplicate row(s) in total.")
    print("  You can now run `python migrate_db.py` to enforce the unique constraint.")
