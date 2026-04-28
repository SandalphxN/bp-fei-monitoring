import os
from typing import List, Optional

import pandas as pd

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras

    def _get_conn():
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url)

    PLACEHOLDER = "%s"
    _IS_PG = True
else:
    import sqlite3

    DB_PATH = os.path.join(os.getcwd(), "data", "app.db")

    def _get_conn():
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    PLACEHOLDER = "?"
    _IS_PG = False


def _execute(conn, sql: str, params=()) -> None:
    sql = sql.replace("?", PLACEHOLDER)
    conn.cursor().execute(sql, params)


def _executemany(conn, sql: str, rows) -> None:
    sql = sql.replace("?", PLACEHOLDER)
    conn.cursor().executemany(sql, rows)


def _fetchall(conn, sql: str, params=()):
    sql = sql.replace("?", PLACEHOLDER)
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur.fetchall()

def init_db():
    conn = _get_conn()
    c = conn.cursor()

    if _IS_PG:
        c.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id SERIAL PRIMARY KEY,
                faculty TEXT NOT NULL,
                year INTEGER NOT NULL,
                filename TEXT NOT NULL,
                content BYTEA,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id SERIAL PRIMARY KEY,
                upload_id INTEGER NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
                year INTEGER,
                year_display TEXT,
                faculty TEXT,
                area TEXT,
                area_type TEXT,
                degree TEXT,
                indicator_code TEXT,
                indicator_name TEXT,
                value REAL,
                is_percentage INTEGER,
                category TEXT,
                program TEXT,
                sub_type TEXT,
                snapshot_type TEXT,
                study_year TEXT
            )
        """)
    else:
        c.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty TEXT NOT NULL,
                year INTEGER NOT NULL,
                filename TEXT NOT NULL,
                content BLOB,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                upload_id INTEGER NOT NULL,
                year INTEGER,
                year_display TEXT,
                faculty TEXT,
                area TEXT,
                area_type TEXT,
                degree TEXT,
                indicator_code TEXT,
                indicator_name TEXT,
                value REAL,
                is_percentage INTEGER,
                category TEXT,
                program TEXT,
                sub_type TEXT,
                snapshot_type TEXT,
                study_year TEXT,
                FOREIGN KEY (upload_id) REFERENCES uploads(id) ON DELETE CASCADE
            )
        """)
        # Pridaj stĺpce ak chýbajú (pre staré SQLite DB)
        for col, col_type in [
            ("sub_type", "TEXT"),
            ("snapshot_type", "TEXT"),
            ("study_year", "TEXT"),
        ]:
            try:
                c.execute(f"ALTER TABLE records ADD COLUMN {col} {col_type}")
            except Exception:
                pass

    conn.commit()
    conn.close()

def insert_upload(faculty: str, year: int, filename: str, content: bytes) -> int:
    conn = _get_conn()
    c = conn.cursor()
    if _IS_PG:
        c.execute(
            "INSERT INTO uploads (faculty, year, filename, content) VALUES (%s, %s, %s, %s) RETURNING id",
            (faculty, year, filename, psycopg2.Binary(content)),
        )
        upload_id = c.fetchone()[0]
    else:
        c.execute(
            "INSERT INTO uploads (faculty, year, filename, content) VALUES (?, ?, ?, ?)",
            (faculty, year, filename, content),
        )
        upload_id = c.lastrowid
    conn.commit()
    conn.close()
    return upload_id


def insert_records(upload_id: int, df: pd.DataFrame):
    conn = _get_conn()
    rows = []
    for _, row in df.iterrows():
        rows.append((
            upload_id,
            row.get("year"),
            row.get("year_display"),
            row.get("faculty"),
            row.get("area"),
            row.get("area_type"),
            row.get("degree"),
            row.get("indicator_code"),
            row.get("indicator_name"),
            row.get("value"),
            int(bool(row.get("is_percentage", False))),
            row.get("category"),
            row.get("program"),
            row.get("sub_type"),
            row.get("snapshot_type"),
            row.get("study_year"),
        ))
    ph = PLACEHOLDER
    sql = f"""
        INSERT INTO records (
            upload_id, year, year_display, faculty, area, area_type, degree,
            indicator_code, indicator_name, value, is_percentage, category,
            program, sub_type, snapshot_type, study_year
        ) VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
    """
    conn.cursor().executemany(sql, rows)
    conn.commit()
    conn.close()


def delete_records_for_year(faculty: str, year: int):
    conn = _get_conn()
    c = conn.cursor()
    ph = PLACEHOLDER
    c.execute(f"SELECT id FROM uploads WHERE faculty = {ph} AND year = {ph}", (faculty, year))
    upload_ids = [row[0] for row in c.fetchall()]
    if upload_ids:
        placeholders = ",".join([ph] * len(upload_ids))
        c.execute(f"DELETE FROM records WHERE upload_id IN ({placeholders})", upload_ids)
        c.execute(f"DELETE FROM uploads WHERE id IN ({placeholders})", upload_ids)
    conn.commit()
    conn.close()


def delete_upload(upload_id: int):
    conn = _get_conn()
    ph = PLACEHOLDER
    conn.cursor().execute(f"DELETE FROM records WHERE upload_id = {ph}", (upload_id,))
    conn.cursor().execute(f"DELETE FROM uploads WHERE id = {ph}", (upload_id,))
    conn.commit()
    conn.close()


def get_years(faculty: Optional[str] = None) -> List[int]:
    conn = _get_conn()
    ph = PLACEHOLDER
    if faculty:
        rows = _fetchall(conn, f"SELECT DISTINCT year FROM uploads WHERE faculty = {ph} ORDER BY year", (faculty,))
    else:
        rows = _fetchall(conn, "SELECT DISTINCT year FROM uploads ORDER BY year")
    conn.close()
    return [r[0] for r in rows]


def list_faculties() -> List[str]:
    conn = _get_conn()
    rows = _fetchall(conn, "SELECT DISTINCT faculty FROM uploads ORDER BY faculty")
    conn.close()
    return [r[0] for r in rows]


def list_uploads() -> pd.DataFrame:
    conn = _get_conn()
    if _IS_PG:
        df = pd.read_sql_query(
            "SELECT id, faculty, year, filename, uploaded_at FROM uploads ORDER BY uploaded_at DESC",
            conn,
        )
    else:
        df = pd.read_sql_query(
            "SELECT id, faculty, year, filename, uploaded_at FROM uploads ORDER BY uploaded_at DESC",
            conn,
        )
    conn.close()
    return df


def load_records(years: List[int], faculty: Optional[str] = None) -> pd.DataFrame:
    conn = _get_conn()
    ph = PLACEHOLDER
    placeholders = ",".join([ph] * len(years))
    params = list(years)
    if faculty:
        query = f"""
            SELECT r.*
            FROM records r
            JOIN uploads u ON r.upload_id = u.id
            WHERE r.year IN ({placeholders})
              AND u.faculty = {ph}
            ORDER BY u.uploaded_at DESC
        """
        params.append(faculty)
    else:
        query = f"""
            SELECT r.*
            FROM records r
            JOIN uploads u ON r.upload_id = u.id
            WHERE r.year IN ({placeholders})
            ORDER BY u.uploaded_at DESC
        """
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    key_cols = ["year", "area", "degree", "indicator_code", "sub_type",
                "program", "snapshot_type", "study_year"]
    present_keys = [c for c in key_cols if c in df.columns]
    if present_keys and not df.empty:
        df = df.drop_duplicates(subset=present_keys, keep="first")

    return df