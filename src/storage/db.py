import os
import sqlite3
from typing import List, Optional

import pandas as pd

DB_PATH = os.path.join(os.getcwd(), "data", "app.db")


def _get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _get_conn()
    c = conn.cursor()
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
    for col, col_type in [
        ("sub_type", "TEXT"),
        ("snapshot_type", "TEXT"),
        ("study_year", "TEXT"),
    ]:
        try:
            c.execute(f"ALTER TABLE records ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    c.execute("""
        DELETE FROM records
        WHERE indicator_code = 'IV_g'
          AND sub_type IN ('spolu', 'plagiáty', 'plagiáty - Progr')
    """)
    c.execute("""
        DELETE FROM records
        WHERE indicator_code = 'IV_g'
          AND sub_type NOT IN (
            'akademické podvody spolu', 'podvody', 'plagiáty spolu',
            'plagiáty - záverečné práce', 'plagiáty - ZAP', 'plagiáty - OOP'
          )
          AND sub_type IS NOT NULL
    """)

    conn.commit()
    conn.close()


def insert_upload(faculty: str, year: int, filename: str, content: bytes) -> int:
    conn = _get_conn()
    c = conn.cursor()
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
    conn.executemany("""
        INSERT INTO records (
            upload_id, year, year_display, faculty, area, area_type, degree,
            indicator_code, indicator_name, value, is_percentage, category,
            program, sub_type, snapshot_type, study_year
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    conn.close()


def delete_records_for_year(faculty: str, year: int):
    conn = _get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM uploads WHERE faculty = ? AND year = ?",
        (faculty, year),
    )
    upload_ids = [row[0] for row in c.fetchall()]
    if upload_ids:
        placeholders = ",".join("?" * len(upload_ids))
        c.execute(f"DELETE FROM records WHERE upload_id IN ({placeholders})", upload_ids)
        c.execute(f"DELETE FROM uploads WHERE id IN ({placeholders})", upload_ids)
    conn.commit()
    conn.close()


def delete_upload(upload_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM records WHERE upload_id = ?", (upload_id,))
    conn.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
    conn.commit()
    conn.close()


def get_years(faculty: Optional[str] = None) -> List[int]:
    conn = _get_conn()
    if faculty:
        rows = conn.execute(
            "SELECT DISTINCT year FROM uploads WHERE faculty = ? ORDER BY year",
            (faculty,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT year FROM uploads ORDER BY year"
        ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def list_faculties() -> List[str]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT DISTINCT faculty FROM uploads ORDER BY faculty"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def list_uploads() -> pd.DataFrame:
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT id, faculty, year, filename, uploaded_at FROM uploads ORDER BY uploaded_at DESC",
        conn,
    )
    conn.close()
    return df


def load_records(years: List[int], faculty: Optional[str] = None) -> pd.DataFrame:
    conn = _get_conn()
    placeholders = ",".join("?" * len(years))
    params = list(years)
    if faculty:
        query = f"""
            SELECT r.*
            FROM records r
            JOIN uploads u ON r.upload_id = u.id
            WHERE r.year IN ({placeholders})
              AND u.faculty = ?
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