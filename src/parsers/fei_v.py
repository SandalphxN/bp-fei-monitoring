import re
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd

from .fei_iv import _find_next_indicator, _to_float, _is_program_name, _base_record, AREAS, DEGREES


def _is_v5a_prog(s: str) -> bool:
    if not s or len(s) > 50:
        return False
    s = s.split("\n")[0].strip()
    skip = {"FEI", "Elektrotechnika", "Informatika", "ŠP", "Čl.", ""}
    if s in skip:
        return False
    skip_frags = ["Ak je KAP", "bez hodnoty", "podľa ŠO", "podľa ŠP AES"]
    return not any(k in s for k in skip_frags)


def _parse_v5_a(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "V5_a"
    name = "miera uplatniteľnosti absolventov TUKE/ŠP"
    cat = "Čl. V"
    records = []
    end_row = _find_next_indicator(df, row_idx + 1)

    def safe_ratio(cell):
        if cell is None:
            return None
        s = str(cell).strip()
        if s in ("-", "bez\nhodnoty", "bez hodnoty", "") or s.startswith("#"):
            return None
        try:
            return float(s)
        except Exception:
            return None

    def prog_name(cell):
        if cell is None or not pd.notna(cell):
            return None
        s = str(cell).split("\n")[0].strip()
        if not _is_v5a_prog(s):
            return None
        return s

    r0 = df.iloc[row_idx]
    for area, cols in [
        (AREAS[0], [(2, "Bc"), (3, "Ing"), (4, "PhD")]),
        (AREAS[1], [(6, "Bc"), (7, "Ing"), (8, "PhD")]),
        (AREAS[2], [(10, "Bc"), (11, "Ing"), (12, "PhD")]),
    ]:
        for col, deg in cols:
            val = safe_ratio(r0.iloc[col] if col < len(r0) else None)
            records.append(_base_record(year, area, deg, code, name,
                val, True, cat))

    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        e_prog = prog_name(r.iloc[5] if 5 < len(r) else None)
        if e_prog:
            for col, deg in [(6, "Bc"), (7, "Ing"), (8, "PhD")]:
                val = safe_ratio(r.iloc[col] if col < len(r) else None)
                records.append(_base_record(year, AREAS[1], deg, code, name,
                    val, True, cat, program=e_prog))
        i_prog = prog_name(r.iloc[9] if 9 < len(r) else None)
        if i_prog:
            for col, deg in [(10, "Bc"), (11, "Ing"), (12, "PhD")]:
                val = safe_ratio(r.iloc[col] if col < len(r) else None)
                records.append(_base_record(year, AREAS[2], deg, code, name,
                    val, True, cat, program=i_prog))

    return records


class FEIParserV_ABC:
    SHEET = "Ukazovatele - čísla"

    def detect_bytes(self, content: bytes) -> bool:
        try:
            xl = pd.ExcelFile(BytesIO(content))
            return self.SHEET in xl.sheet_names
        except Exception:
            return False

    def parse_bytes(self, content: bytes, year: int) -> pd.DataFrame:
        df_raw = pd.read_excel(BytesIO(content), sheet_name=self.SHEET, header=None)
        return self._parse_df(df_raw, year)

    def _parse_df(self, df: pd.DataFrame, year: int) -> pd.DataFrame:
        all_records: List[Dict] = []
        row_indices: Dict[str, int] = {}
        in_section_v = False

        for i, row in df.iterrows():
            c0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if c0 == "Čl. V.":
                in_section_v = True
                continue
            if in_section_v and c0 in "abcdefghij" and len(c0) == 1:
                if c0 not in row_indices:
                    row_indices[c0] = i

        if "a" in row_indices:
            all_records.extend(_parse_v5_a(df, row_indices["a"], year))

        return pd.DataFrame(all_records) if all_records else pd.DataFrame()