"""
migrate_db.py — One-shot database migration.

Run once:  python migrate_db.py

What it does:
  1. Adds missing columns to `users` (user_type)
  2. Creates new tables: clinic_profiles, clinic_services, clinic_schedules,
     appointments — if they don't exist yet.
  3. Back-fills user_type='CLIENTE' for all existing users.
"""
import sys
import os

# Make sure we can import the Flask app
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from app import app, db  # noqa: import order
from sqlalchemy import text

def column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)

def table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table}
    ).fetchone()
    return row is not None

with app.app_context():
    with db.engine.connect() as conn:
        # ── 1. Add user_type to users ─────────────────────────────────────
        if not column_exists(conn, "users", "user_type"):
            print("Adding users.user_type ...")
            conn.execute(text(
                "ALTER TABLE users ADD COLUMN user_type VARCHAR(20) NOT NULL DEFAULT 'CLIENTE'"
            ))
            conn.commit()
            print("  ✓ users.user_type added and back-filled with 'CLIENTE'")
        else:
            print("  · users.user_type already exists, skipping.")

        # ── 2. Create new tables via SQLAlchemy metadata ──────────────────
        print("Creating new tables (if not exist) ...")
        db.create_all()
        conn.commit()
        print("  ✓ All tables up to date.")

        # ── 3. Add preco to disponibilidades ─────────────────────────────
        if not column_exists(conn, "disponibilidades", "preco"):
            print("Adding disponibilidades.preco ...")
            conn.execute(text(
                "ALTER TABLE disponibilidades ADD COLUMN preco FLOAT"
            ))
            conn.commit()
            print("  ✓ disponibilidades.preco added (NULL = usa preco_padrao do anuncio).")
        else:
            print("  · disponibilidades.preco already exists, skipping.")

        # ── 4. Add valor_ajuste to disponibilidades ───────────────────────
        if not column_exists(conn, "disponibilidades", "valor_ajuste"):
            print("Adding disponibilidades.valor_ajuste ...")
            conn.execute(text(
                "ALTER TABLE disponibilidades ADD COLUMN valor_ajuste FLOAT"
            ))
            conn.commit()
            print("  ✓ disponibilidades.valor_ajuste added (delta: + acrescimo, - desconto).")
        else:
            print("  · disponibilidades.valor_ajuste already exists, skipping.")

        # ── 5. Add extended address columns to clinic_services ────────────
        addr_cols = [
            ("complemento",      "VARCHAR(100)"),
            ("estado",           "VARCHAR(2)"),
            ("cep",              "VARCHAR(9)"),
            ("google_maps_link", "VARCHAR(500)"),
        ]
        for col_name, col_type in addr_cols:
            if not column_exists(conn, "clinic_services", col_name):
                print(f"Adding clinic_services.{col_name} ...")
                conn.execute(text(
                    f"ALTER TABLE clinic_services ADD COLUMN {col_name} {col_type}"
                ))
                conn.commit()
                print(f"  ✓ clinic_services.{col_name} added.")
            else:
                print(f"  · clinic_services.{col_name} already exists, skipping.")

        # ── 6. Add appointment_id FK to reviews (post-care integrity) ─────
        if not column_exists(conn, "reviews", "appointment_id"):
            print("Adding reviews.appointment_id ...")
            conn.execute(text(
                "ALTER TABLE reviews ADD COLUMN appointment_id INTEGER REFERENCES appointments(id)"
            ))
            conn.commit()
            print("  ✓ reviews.appointment_id added.")
        else:
            print("  · reviews.appointment_id already exists, skipping.")

        # ── 7. Create post_atendimentos table (new) via SQLAlchemy ─────────
        print("Creating post_atendimentos table (if not exists) ...")
        db.create_all()
        conn.commit()
        print("  ✓ post_atendimentos table up to date.")

    print("\nMigration complete. You can now start the app normally.")


# ── 6. Unique index on disponibilidades(service_id, data, horario) ────────────
with app.app_context():
    with db.engine.connect() as conn:
        idx_name = "uq_disp_service_data_hora"
        idx_exists = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND name=:n"),
            {"n": idx_name}
        ).fetchone()
        if not idx_exists:
            print("Creating unique index on disponibilidades(service_id, data, horario) ...")
            try:
                conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_disp_service_data_hora "
                    "ON disponibilidades(service_id, data, horario)"
                ))
                conn.commit()
                print("  ✓ Unique index created.")
            except Exception as exc:
                conn.rollback()
                print(f"  ! Could not create index (duplicate data exists?): {exc}")
                print("    Run cleanup_duplicates.py first, then re-run migrate_db.py.")
        else:
            print("  · Unique index uq_disp_service_data_hora already exists, skipping.")
