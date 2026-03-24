import re
from io import BytesIO
from typing import Dict, List, Optional

import pandas as pd

INVALID_TOKENS = {"-", ".", "", "#####", "######", "nan"}

AREAS = [
    {"name": "FEI",              "col_name": 2,  "col_prog": None, "type": "faculty"},
    {"name": "Elektrotechnika",  "col_name": 6,  "col_prog": 5,   "type": "area"},
    {"name": "Informatika",      "col_name": 10, "col_prog": 9,   "type": "area"},
]

DEGREES = ["Bc", "Ing", "PhD"]


def _to_float(value) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if s in INVALID_TOKENS:
        return None
    try:
        return float(value)
    except Exception:
        try:
            return float(s.replace(",", "."))
        except Exception:
            return None


def _is_program_name(s: str) -> bool:
    if not s or len(s) > 40:
        return False
    exact_skip = {"FEI", "Elektrotechnika", "Informatika"}
    if s in exact_skip:
        return False
    skip = [
        "ŠP v MAIS", "všetci", "ukončení", "zapísaní", "zahraniční",
        "vylúčenie", "zanechanie", "zmena ŠP", "Čísla", "Detaily",
        "Súčet", "Počet", "Predčasné", "en /", "iní", "neotvorené",
        "ponúkané", "ostatní", "INF+KB",
    ]
    return not any(k in s for k in skip)


def _base_record(year: int, area: dict, degree: str, code: str,
                 name: str, value, is_pct: bool,
                 category: str, program=None,
                 sub_type=None, snapshot_type=None, study_year=None) -> Dict:
    return {
        "year": year,
        "year_display": f"{year}-{year+1}",
        "faculty": "FEI",
        "area": area["name"],
        "area_type": area["type"],
        "degree": degree,
        "indicator_code": code,
        "indicator_name": name,
        "value": _to_float(value),
        "is_percentage": is_pct,
        "category": category,
        "program": program,
        "sub_type": sub_type,
        "snapshot_type": snapshot_type,
        "study_year": study_year,
    }

def _parse_multiline_rocniky(cell_str: str):
    import re as _re
    results = []
    after_sep = False
    for line in str(cell_str).split("\n"):
        line = line.strip()
        if line.startswith("---"):
            after_sep = True
            continue
        if after_sep:
            val = _to_float(line)
            if val is not None:
                results.append(("všetci", val))
            break
        m = _re.match(r"(\d+r)\s*:\s*(.+)", line)
        if m:
            rlabel = m.group(1)
            val = _to_float(m.group(2).strip())
            results.append((rlabel, val))
    return results


def _parse_iv_a(df, row_idx: int, year: int):
    records = []
    code = "IV_a"
    name = "počet študentov TUKE/ŠP v jednotlivých rokoch štúdia"
    cat = "Čl. IV - 1 - Prijímacie konanie, priebeh a ukončenie štúdia"

    row = df.iloc[row_idx]
    for area in AREAS:
        for di, deg in enumerate(DEGREES):
            col = area["col_name"] + di
            records.append(_base_record(year, area, deg, code, name,
                row.iloc[col], False, cat, snapshot_type="ZS", study_year="všetci"))

    rocnik_area_map = [
        (AREAS[0], 5, 2, 3, 4),
        (AREAS[1], 5, 6, 7, 8),
        (AREAS[2], 9, 10, 11, 12),
    ]
    for offset in range(1, 7):
        if row_idx + offset >= len(df):
            break
        r = df.iloc[row_idx + offset]
        found_any = False
        for (area, lcol, bc_col, ing_col, phd_col) in rocnik_area_map:
            lbl_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(lbl_cell):
                continue
            lbl = str(lbl_cell).strip()
            m = re.match(r"všetci\s+(\d+r)", lbl)
            if not m:
                continue
            rlabel = m.group(1)
            found_any = True
            for col, deg in [(bc_col, "Bc"), (ing_col, "Ing"), (phd_col, "PhD")]:
                val = r.iloc[col] if col < len(r) else None
                records.append(_base_record(year, area, deg, code, name,
                    val, False, cat, snapshot_type="ZS", study_year=rlabel))
        if not found_any:
            break

    spring_row_idx = None
    for scan in range(row_idx + 1, min(row_idx + 30, len(df))):
        cell1 = str(df.iloc[scan, 1]).strip() if pd.notna(df.iloc[scan, 1]) else ""
        if "1.roč" in cell1 and "31.3" in cell1:
            spring_row_idx = scan
            break

    prog_start = row_idx + 6
    prog_end = spring_row_idx if spring_row_idx else row_idx + 25
    for i in range(prog_start, prog_end):
        if i >= len(df):
            break
        r = df.iloc[i]
        for (area, lcol, bc_col, ing_col, phd_col) in rocnik_area_map:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if not _is_program_name(prog_str):
                continue
            for col, deg in [(bc_col, "Bc"), (ing_col, "Ing"), (phd_col, "PhD")]:
                cell_val = r.iloc[col] if col < len(r) else None
                if not pd.notna(cell_val):
                    continue
                cell_str = str(cell_val).strip()
                if "\n" in cell_str or re.match(r"\d+r\s*:", cell_str):
                    for (rlabel, val) in _parse_multiline_rocniky(cell_str):
                        records.append(_base_record(year, area, deg, code, name,
                            val, False, cat, program=prog_str,
                            snapshot_type="ZS", study_year=rlabel))
                else:
                    records.append(_base_record(year, area, deg, code, name,
                        cell_str, False, cat, program=prog_str,
                        snapshot_type="ZS", study_year="všetci"))

    if spring_row_idx is not None:
        r_spring = df.iloc[spring_row_idx]
        for area, bc_col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
            val = r_spring.iloc[bc_col] if bc_col < len(r_spring) else None
            records.append(_base_record(year, area, "Bc", code, name,
                val, False, cat, snapshot_type="LS", study_year="1r"))
        for i in range(spring_row_idx + 1, min(spring_row_idx + 20, len(df))):
            r2 = df.iloc[i]
            for (area, lcol, bc_col, _i, _j) in rocnik_area_map:
                prog_cell = r2.iloc[lcol] if lcol < len(r2) else None
                if not pd.notna(prog_cell):
                    continue
                prog_str = str(prog_cell).strip()
                if not _is_program_name(prog_str):
                    continue
                val = r2.iloc[bc_col] if bc_col < len(r2) else None
                records.append(_base_record(year, area, "Bc", code, name,
                    val, False, cat, program=prog_str,
                    snapshot_type="LS", study_year="1r"))

    return records

_BC_SUBTYPES_ZS = {
    "vylúčenie po ZS":  "vylúčenie",
    "zanechanie po ZS": "zanechanie",
    "zmena ŠP po ZS":   "zmena ŠP",
    "vylúčenie":        "vylúčenie",
    "zanechanie":       "zanechanie",
    "zmena ŠP":        "zmena ŠP",
}
_BC_SUBTYPES_LS = {
    "vylúčenie po LS":  "vylúčenie",
    "zanechanie po LS": "zanechanie",
    "zmena ŠP po LS":   "zmena ŠP",
}


def _parse_iv_bc(df: pd.DataFrame, row_idx: int, year: int,
                 ind_code: str, ind_name: str) -> List[Dict]:
    records: List[Dict] = []
    cat = "Čl. IV - 1 - Prijímacie konanie, priebeh a ukončenie štúdia"
    is_pct = True

    row = df.iloc[row_idx]
    for area in AREAS:
        for di, deg in enumerate(DEGREES):
            col = area["col_name"] + di
            records.append(_base_record(
                year, area, deg, ind_code, ind_name,
                row.iloc[col], is_pct, cat,
                sub_type="spolu", snapshot_type="ZS",
            ))

    for offset in range(1, 4):
        r = df.iloc[row_idx + offset]
        lbl_raw = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""
        sub = _BC_SUBTYPES_ZS.get(lbl_raw)
        if sub is None:
            continue
        for area in AREAS:
            for di, deg in enumerate(DEGREES):
                col = area["col_name"] + di
                records.append(_base_record(
                    year, area, deg, ind_code, ind_name,
                    r.iloc[col], is_pct, cat,
                    sub_type=sub, snapshot_type="ZS",
                ))

    zs_prog_start = row_idx + 4
    ls_row_idx = _find_ls_row(df, row_idx, ind_code)

    _parse_prog_block(
        df, zs_prog_start, ls_row_idx if ls_row_idx else row_idx + 35,
        year, ind_code, ind_name, is_pct, cat, "ZS", records,
    )

    if ls_row_idx is None:
        return records

    r_ls = df.iloc[ls_row_idx]
    for area in AREAS:
        for di, deg in enumerate(DEGREES):
            col = area["col_name"] + di
            records.append(_base_record(
                year, area, deg, ind_code, ind_name,
                r_ls.iloc[col], is_pct, cat,
                sub_type="spolu", snapshot_type="LS",
            ))

    for offset in range(1, 4):
        if ls_row_idx + offset >= len(df):
            break
        r = df.iloc[ls_row_idx + offset]
        lbl_raw = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""
        sub = _BC_SUBTYPES_LS.get(lbl_raw)
        if sub is None:
            continue
        for area in AREAS:
            for di, deg in enumerate(DEGREES):
                col = area["col_name"] + di
                records.append(_base_record(
                    year, area, deg, ind_code, ind_name,
                    r.iloc[col], is_pct, cat,
                    sub_type=sub, snapshot_type="LS",
                ))

    ls_prog_start = ls_row_idx + 4
    next_indicator_row = _find_next_indicator(df, ls_row_idx + 1)
    _parse_prog_block(
        df, ls_prog_start, next_indicator_row,
        year, ind_code, ind_name, is_pct, cat, "LS", records,
    )

    return records


def _find_ls_row(df: pd.DataFrame, start: int, ind_code: str) -> Optional[int]:
    for i in range(start + 1, min(start + 60, len(df))):
        c5 = str(df.iloc[i, 5]).strip() if pd.notna(df.iloc[i, 5]) else ""
        c1 = str(df.iloc[i, 1]).strip() if pd.notna(df.iloc[i, 1]) else ""
        if "LS" in c5 or ("ukončení" in c5 and "LS" in c5):
            return i
        if "LS" in c1 and ("ukončení" in c1 or "1roč" in c1):
            return i
    for i in range(start + 1, min(start + 60, len(df))):
        c5 = str(df.iloc[i, 5]).strip() if pd.notna(df.iloc[i, 5]) else ""
        if "LS" in c5:
            return i
        c2_val = df.iloc[i, 2]
        c1_val = str(df.iloc[i, 1]).strip() if pd.notna(df.iloc[i, 1]) else ""
        if (pd.notna(c2_val) and c2_val not in ["-", "."]
                and "vylúčenie" not in c1_val
                and "zanechanie" not in c1_val
                and "zmena" not in c1_val
                and "Predčasné" not in c1_val
                and i > start + 10):
            return i
    return None


def _find_next_indicator(df: pd.DataFrame, start: int) -> int:
    for i in range(start, min(start + 80, len(df))):
        c0 = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ""
        if c0 in list("abcdefghijklmnopqrstuvwxyz") and len(c0) == 1:
            return i
    return min(start + 80, len(df))


def _parse_prog_block(df, start, end, year, code, name, is_pct, cat,
                      snapshot_type, records):
    for i in range(start, min(end, len(df))):
        row = df.iloc[i]
        for area in [AREAS[1], AREAS[2]]:
            cp = area["col_prog"]
            if cp is None or cp >= len(row):
                continue
            cell = row.iloc[cp]
            if not pd.notna(cell):
                continue
            cell_str = str(cell).strip()
            if "\n" not in cell_str:
                continue
            parts = cell_str.split("\n", 1)
            prog = parts[0].strip()
            sub = parts[1].strip() if len(parts) > 1 else None
            if not _is_program_name(prog):
                continue
            val = row.iloc[area["col_name"]]   # Bc column (only Bc for b/c)
            records.append(_base_record(
                year, area, "Bc", code, name,
                val, is_pct, cat,
                program=prog, sub_type=sub, snapshot_type=snapshot_type,
            ))

def _parse_iv_d(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records: List[Dict] = []
    code = "IV_d"
    name = "podiel zahraničných študentov z celkového počtu študentov"
    cat = "Čl. IV - 1 - Prijímacie konanie, priebeh a ukončenie štúdia"

    row = df.iloc[row_idx]
    for area in AREAS:
        for di, deg in enumerate(DEGREES):
            col = area["col_name"] + di
            records.append(_base_record(year, area, deg, code, name,
                row.iloc[col], True, cat, snapshot_type="ZS", study_year="všetci"))

    rocnik_area_map = [
        (AREAS[1], 5, 6, 7, 8),
        (AREAS[2], 9, 10, 11, 12),
    ]
    for offset in range(1, 7):
        if row_idx + offset >= len(df):
            break
        r = df.iloc[row_idx + offset]
        found_any = False
        for (area, lcol, bc_col, ing_col, phd_col) in rocnik_area_map:
            lbl_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(lbl_cell):
                continue
            lbl = str(lbl_cell).strip()
            m = re.match(r"všetci\s+(\d+r)", lbl)
            if not m:
                continue
            rlabel = m.group(1)
            found_any = True
            for col, deg in [(bc_col, "Bc"), (ing_col, "Ing"), (phd_col, "PhD")]:
                val = r.iloc[col] if col < len(r) else None
                records.append(_base_record(year, area, deg, code, name,
                    val, True, cat, snapshot_type="ZS", study_year=rlabel))
        if not found_any:
            break

    for offset in range(1, 7):
        if row_idx + offset >= len(df):
            break
        r = df.iloc[row_idx + offset]
        lbl_cell = r.iloc[5] if 5 < len(r) else None
        if not pd.notna(lbl_cell):
            break
        lbl = str(lbl_cell).strip()
        m = re.match(r"všetci\s+(\d+r)", lbl)
        if not m:
            break
        rlabel = m.group(1)
        for fi, deg in [(2, "Bc"), (3, "Ing"), (4, "PhD")]:
            val_f = r.iloc[fi] if fi < len(r) else None
            records.append(_base_record(year, AREAS[0], deg, code, name,
                val_f, True, cat, snapshot_type="ZS", study_year=rlabel))

    spring_row_idx = None
    for scan in range(row_idx + 1, min(row_idx + 25, len(df))):
        cell1 = str(df.iloc[scan, 1]).strip() if pd.notna(df.iloc[scan, 1]) else ""
        if "1.roč" in cell1 and "31.3" in cell1:
            spring_row_idx = scan
            break

    if spring_row_idx is not None:
        r_spring = df.iloc[spring_row_idx]
        for area, bc_col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
            val = r_spring.iloc[bc_col] if bc_col < len(r_spring) else None
            records.append(_base_record(year, area, "Bc", code, name,
                val, True, cat, snapshot_type="LS", study_year="1r"))

    return records

def _parse_iv_e(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records: List[Dict] = []
    code = "IV_e"
    name = "podiel študentov s iným ako slovenským občianstvom študujúcich v inom ako slovenskom jazyku z celkového počtu študentov"
    cat = "Čl. IV - 1 - Prijímacie konanie, priebeh a ukončenie štúdia"

    row = df.iloc[row_idx]
    for area in AREAS:
        for di, deg in enumerate(DEGREES):
            col = area["col_name"] + di
            records.append(_base_record(year, area, deg, code, name,
                row.iloc[col], True, cat, snapshot_type="ZS", study_year="všetci"))

    if row_idx + 1 < len(df):
        r_spring = df.iloc[row_idx + 1]
        cell1 = str(r_spring.iloc[1]).strip() if pd.notna(r_spring.iloc[1]) else ""
        if "1.roč" in cell1 and "31.3" in cell1:
            for area, bc_col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
                val = r_spring.iloc[bc_col] if bc_col < len(r_spring) else None
                records.append(_base_record(year, area, "Bc", code, name,
                    val, True, cat, snapshot_type="LS", study_year="1r"))

    return records

def _parse_iv_f(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records: List[Dict] = []
    code = "IV_f"
    name = "počet študentov prekračujúcich štandardnú dĺžku štúdia"
    cat = "Čl. IV - 1 - Prijímacie konanie, priebeh a ukončenie štúdia"

    row = df.iloc[row_idx]
    for area in AREAS:
        for di, deg in enumerate(DEGREES):
            col = area["col_name"] + di
            records.append(_base_record(year, area, deg, code, name,
                row.iloc[col], False, cat))

    for offset in range(1, 30):
        ri = row_idx + offset
        if ri >= len(df):
            break
        r = df.iloc[ri]
        c0 = str(r.iloc[0]).strip() if pd.notna(r.iloc[0]) else ""
        if c0 not in ("", "-"):
            break

        e_name_cell = r.iloc[5] if 5 < len(r) else None
        if pd.notna(e_name_cell):
            prog = str(e_name_cell).strip()
            if prog and prog not in ("-", "ŠP v MAIS", ""):
                for di, deg in enumerate(DEGREES):
                    col = 6 + di
                    val = r.iloc[col] if col < len(r) else None
                    records.append(_base_record(year, AREAS[1], deg, code, name,
                        val, False, cat, program=prog))

        i_name_cell = r.iloc[9] if 9 < len(r) else None
        if pd.notna(i_name_cell):
            prog = str(i_name_cell).strip()
            if prog and prog not in ("-", "ŠP v MAIS", ""):
                for di, deg in enumerate(DEGREES):
                    col = 10 + di
                    val = r.iloc[col] if col < len(r) else None
                    records.append(_base_record(year, AREAS[2], deg, code, name,
                        val, False, cat, program=prog))

    return records

_G_SUBTYPES_PARTIAL = [
    ("odhalené podvody",           "podvody"),
    ("plagiáty - záverečné práce", "plagiáty - záverečné práce"),
    ("plagiáty - predmet ZAP",     "plagiáty - ZAP"),
    ("plagiáty - predmet Progr",   None),
    ("plagiáty - predmet OOP",     "plagiáty - OOP"),
    ("plagiáty",                   "plagiáty spolu"),
]


def _g_subtype_from_label(label: str) -> Optional[str]:
    for prefix, canonical in _G_SUBTYPES_PARTIAL:
        if label.startswith(prefix):
            return canonical
    return ""


def _parse_iv_g(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records: List[Dict] = []
    code = "IV_g"
    name = "počet odhalených akademických podvodov, z toho počet plagiátov"
    cat = "Čl. IV - 1 - Prijímacie konanie, priebeh a ukončenie štúdia"

    end_row = _find_next_indicator(df, row_idx + 1)

    row = df.iloc[row_idx]
    for area, bc_col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        val = row.iloc[bc_col] if bc_col < len(row) else None
        records.append(_base_record(year, area, "Bc", code, name,
            val, False, cat, sub_type="akademické podvody spolu"))

    current_subtype: Optional[str] = None
    has_plagiaty_spolu = False

    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        c1 = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""

        subtype_match = _g_subtype_from_label(c1) if c1 else ""
        if subtype_match is None:
            current_subtype = None
            continue
        if subtype_match != "":
            current_subtype = subtype_match
            if current_subtype == "plagiáty spolu":
                has_plagiaty_spolu = True
            for area, bc_col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
                val = r.iloc[bc_col] if bc_col < len(r) else None
                records.append(_base_record(year, area, "Bc", code, name,
                    val, False, cat, sub_type=current_subtype))
            continue

        if current_subtype is None:
            continue
        if current_subtype not in ("plagiáty - ZAP",):
            continue

        prog_areas = [
            (AREAS[1], 5, 6),
            (AREAS[2], 9, 10),
        ]
        for (area, lcol, bc_col) in prog_areas:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if not _is_program_name(prog_str):
                continue
            val = r.iloc[bc_col] if bc_col < len(r) else None
            records.append(_base_record(year, area, "Bc", code, name,
                val, False, cat, program=prog_str, sub_type=current_subtype))

    if not has_plagiaty_spolu:
        df_tmp = pd.DataFrame(records)
        for area in AREAS:
            spolu_rows = df_tmp[(df_tmp["area"] == area["name"]) &
                                (df_tmp["sub_type"] == "akademické podvody spolu") &
                                (df_tmp["program"].isna())]
            podvody_rows = df_tmp[(df_tmp["area"] == area["name"]) &
                                  (df_tmp["sub_type"] == "podvody") &
                                  (df_tmp["program"].isna())]
            spolu_val = spolu_rows["value"].iloc[0] if not spolu_rows.empty else None
            podvody_val = podvody_rows["value"].iloc[0] if not podvody_rows.empty else None
            if spolu_val is not None:
                plagiaty_val = (spolu_val - (podvody_val or 0)) if spolu_val is not None else None
                records.append(_base_record(year, area, "Bc", code, name,
                    plagiaty_val, False, cat, sub_type="plagiáty spolu"))

    return records

def _parse_iv_h(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records: List[Dict] = []
    code = "IV_h"
    name = "počet disciplinárnych konaní (vylúčenie zo štúdia, napomenutie, pod.)"
    cat = "Čl. IV - 1 - Prijímacie konanie, priebeh a ukončenie štúdia"

    row = df.iloc[row_idx]
    for area in AREAS:
        for di, deg in enumerate(DEGREES):
            col = area["col_name"] + di
            records.append(_base_record(year, area, deg, code, name,
                row.iloc[col], False, cat))

    return records

_I_SKIP_COL1 = {"Úspešnosť", "úspešnosť"}


def _i_is_file_ref(label: str) -> bool:
    return any(label.startswith(s) for s in _I_SKIP_COL1)


def _parse_iv_i(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:

    records: List[Dict] = []
    code = "IV_i"
    name = "počet absolventov"
    cat = "Čl. IV - 1 - Prijímacie konanie, priebeh a ukončenie štúdia"

    row = df.iloc[row_idx]
    for area in AREAS:
        for di, deg in enumerate(DEGREES):
            col = area["col_name"] + di
            records.append(_base_record(year, area, deg, code, name,
                row.iloc[col], False, cat))

    end_row = _find_next_indicator(df, row_idx + 1)

    prog_areas = [
        (AREAS[1], 5, 6, 7, 8),
        (AREAS[2], 9, 10, 11, 12),
    ]

    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]

        c1 = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""
        if _i_is_file_ref(c1):
            continue

        for (area, lcol, bc_col, ing_col, phd_col) in prog_areas:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if not _is_program_name(prog_str):
                continue
            for col, deg in [(bc_col, "Bc"), (ing_col, "Ing"), (phd_col, "PhD")]:
                val = r.iloc[col] if col < len(r) else None
                records.append(_base_record(year, area, deg, code, name,
                    val, False, cat, program=prog_str))

    return records

class FEIParserIV_ABC:
    SHEET = "Čl. IV - 1 - čísla"

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

        row_indices = {}
        for i, row in df.iterrows():
            c0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if c0 in "abcdefghi" and len(c0) == 1 and c0 not in row_indices:
                row_indices[c0] = i

        if "a" in row_indices:
            all_records.extend(_parse_iv_a(df, row_indices["a"], year))

        if "b" in row_indices:
            all_records.extend(_parse_iv_bc(
                df, row_indices["b"], year,
                "IV_b",
                "podiel študentov prvého roku štúdia, ktorí predčasne ukončili štúdium po ZS/LS",
            ))

        if "c" in row_indices:
            all_records.extend(_parse_iv_bc(
                df, row_indices["c"], year,
                "IV_c",
                "miera predčasného ukončenia štúdia (okrem 1. ročníka)",
            ))

        if "d" in row_indices:
            all_records.extend(_parse_iv_d(df, row_indices["d"], year))

        if "e" in row_indices:
            all_records.extend(_parse_iv_e(df, row_indices["e"], year))

        if "f" in row_indices:
            all_records.extend(_parse_iv_f(df, row_indices["f"], year))

        if "g" in row_indices:
            all_records.extend(_parse_iv_g(df, row_indices["g"], year))

        if "h" in row_indices:
            all_records.extend(_parse_iv_h(df, row_indices["h"], year))

        if "i" in row_indices:
            all_records.extend(_parse_iv_i(df, row_indices["i"], year))

        return pd.DataFrame(all_records)

_IV2_SKIP_TOKENS = {
    "študenti / učitelia", "práce / vedúci", "len počet",
    "PE a ApE na Ing spojené", "vedúci", "študenti /",
}


def _is_iv2_prog(s: str) -> bool:
    if not s or len(s) > 40:
        return False
    if s in {"FEI", "Elektrotechnika", "Informatika"}:
        return False
    if s in _IV2_SKIP_TOKENS:
        return False
    skip_fragments = [
        "Čísla", "Počítame", "Koľko", "PE má", "započítan", "extern",
        "len počty", "podiel", "vyslan",
    ]
    if any(k in s for k in skip_fragments):
        return False
    return True


def _parse_iv2_a(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV2_a"
    name = "pomer počtu študentov a učiteľov"
    cat  = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    records: List[Dict] = []

    end_row = _find_next_indicator(df, row_idx + 1)
    current_sub: Optional[str] = "Bc a Ing k 31.10"

    r0 = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        val = _to_float(r0.iloc[col] if col < len(r0) else None)
        records.append(_base_record(year, area, "ratio", code, name,
            val, False, cat, sub_type=current_sub))

    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        c1 = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""

        if c1.startswith("Čísla Bc, 1.roč"):
            current_sub = "Bc 1.roč k 31.3"
            for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
                val = _to_float(r.iloc[col] if col < len(r) else None)
                records.append(_base_record(year, area, "ratio", code, name,
                    val, False, cat, sub_type=current_sub))
            continue

        for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if not _is_iv2_prog(prog_str):
                continue
            if area == AREAS[2]:
                if prog_str == "KB":
                    continue
                if prog_str == "INF":
                    prog_str = "INF+KB"
            val = _to_float(r.iloc[vcol] if vcol < len(r) else None)
            records.append(_base_record(year, area, "ratio", code, name,
                val, False, cat, program=prog_str, sub_type=current_sub))

    return records


def _parse_iv2_b(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV2_b"
    name = "počet záverečných prác vedených vedúcim záverečnej práce"
    cat  = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    records: List[Dict] = []

    end_row = _find_next_indicator(df, row_idx + 1)

    SUB_ALL    = "všetci učitelia"
    SUB_OBS    = "obsadení vedúci"
    SUB_COUNTS = "len počty vrátane DzP"

    current_sub: Optional[str] = SUB_ALL
    counts_mode = False

    r0 = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        val = _to_float(r0.iloc[col] if col < len(r0) else None)
        records.append(_base_record(year, area, "ratio", code, name,
            val, False, cat, sub_type=current_sub))

    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        c1 = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""

        if c1.startswith("započítaní len obsadení"):
            current_sub = SUB_OBS
            counts_mode = False
            for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
                v = r.iloc[col] if col < len(r) else None
                if pd.notna(v):
                    records.append(_base_record(year, area, "ratio", code, name,
                        _to_float(v), False, cat, sub_type=current_sub))
            continue

        if c1.startswith("len počty záverečných"):
            current_sub = SUB_COUNTS
            counts_mode = True
            for col, deg in [(2, "Bc"), (3, "Ing"), (4, "PhD")]:
                raw = r.iloc[col] if col < len(r) else None
                val = _to_float(raw)
                if val is not None:
                    val = round(val)
                records.append(_base_record(year, AREAS[0], deg, code, name,
                    val, False, cat, sub_type=current_sub))
            for col, deg in [(10, "Bc"), (11, "Ing"), (12, "PhD")]:
                raw = r.iloc[col] if col < len(r) else None
                val = _to_float(raw)
                if val is not None and val >= 1:
                    val = round(val)
                elif val is not None and val < 1:
                    val = None
                records.append(_base_record(year, AREAS[2], deg, code, name,
                    val, False, cat, sub_type=current_sub))
            continue

        if counts_mode:
            prog_cell = r.iloc[9] if 9 < len(r) else None
            if pd.notna(prog_cell):
                prog_str = str(prog_cell).strip()
                if _is_iv2_prog(prog_str):
                    for col, deg in [(10, "Bc"), (11, "Ing"), (12, "PhD")]:
                        raw = r.iloc[col] if col < len(r) else None
                        val = _to_float(raw)
                        if val is not None and val >= 1:
                            val = round(val)
                        elif val is not None and val < 1:
                            val = None
                        records.append(_base_record(year, AREAS[2], deg, code, name,
                            val, False, cat, program=prog_str, sub_type=current_sub))
        else:
            for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
                prog_cell = r.iloc[lcol] if lcol < len(r) else None
                if not pd.notna(prog_cell):
                    continue
                prog_str = str(prog_cell).strip()
                if not _is_iv2_prog(prog_str):
                    continue
                val = _to_float(r.iloc[vcol] if vcol < len(r) else None)
                records.append(_base_record(year, area, "ratio", code, name,
                    val, False, cat, program=prog_str, sub_type=current_sub))

    return records


_IV2_CDEF_LABEL_SKIP = {
    "vyslaní / všetci", "ŠP", "odhad",
    "FEI", "Elektrotechnika", "Informatika",
}


def _iv2_cdef_is_prog(s: str) -> bool:
    if not s or len(s) > 40:
        return False
    if s in _IV2_CDEF_LABEL_SKIP:
        return False
    skip_frags = ["Zoznam", "odhadované", "poradenstvo", "zamestnancov so",
                  "štúdia", "kariérne", "všetkých"]
    return not any(k in s for k in skip_frags)


def _parse_iv2_c(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records = []
    code = "IV2_c"
    name = "podiel vyslaných študentov na mobility do zahraničia z celkového počtu študentov"
    cat = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    row = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        for di, deg in enumerate(DEGREES):
            c = col + di
            records.append(_base_record(year, area, deg, code, name,
                _to_float(row.iloc[c] if c < len(row) else None), True, cat))
    end_row = _find_next_indicator(df, row_idx + 1)
    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        for area, lcol, bc_col, ing_col, phd_col in [
                (AREAS[1], 5, 6, 7, 8), (AREAS[2], 9, 10, 11, 12)]:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if not _iv2_cdef_is_prog(prog_str):
                continue
            for col, deg in [(bc_col, "Bc"), (ing_col, "Ing"), (phd_col, "PhD")]:
                records.append(_base_record(year, area, deg, code, name,
                    _to_float(r.iloc[col] if col < len(r) else None), True, cat, program=prog_str))
    return records


def _parse_iv2_d(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records = []
    code = "IV2_d"
    name = "počet prijatých študentov na mobility zo zahraničia v príslušnom akademickom roku"
    cat = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    row = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        for di, deg in enumerate(DEGREES):
            c = col + di
            records.append(_base_record(year, area, deg, code, name,
                _to_float(row.iloc[c] if c < len(row) else None), False, cat))
    return records


def _parse_iv2_e(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records = []
    code = "IV2_e"
    name = "rozsah podpory a služieb kariérneho poradenstva (odhadované v hodinách na študenta)"
    cat = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    row = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        for di, deg in enumerate(DEGREES):
            c = col + di
            records.append(_base_record(year, area, deg, code, name,
                _to_float(row.iloc[c] if c < len(row) else None), False, cat))
    return records


def _parse_iv2_f(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    records = []
    code = "IV2_f"
    name = "počet zamestnancov so zameraním na podporu študentov (študijné a kariérne poradenstvo)"
    cat = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    row = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        for di, deg in enumerate(DEGREES):
            c = col + di
            records.append(_base_record(year, area, deg, code, name,
                _to_float(row.iloc[c] if c < len(row) else None), False, cat))
    end_row = _find_next_indicator(df, row_idx + 1)
    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        for area, lcol, bc_col, ing_col, phd_col in [
                (AREAS[1], 5, 6, 7, 8), (AREAS[2], 9, 10, 11, 12)]:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if not _iv2_cdef_is_prog(prog_str):
                continue
            for col, deg in [(bc_col, "Bc"), (ing_col, "Ing"), (phd_col, "PhD")]:
                records.append(_base_record(year, area, deg, code, name,
                    _to_float(r.iloc[col] if col < len(r) else None), False, cat, program=prog_str))
    return records



_G_PROG_SKIP = {"účasť ak.rok", "účasť ZS", "účasť LS",
                "FEI", "Elektrotechnika", "Informatika"}


def _iv2_g_is_prog(s: str) -> bool:
    if not s or len(s) > 40:
        return False
    if s in _G_PROG_SKIP:
        return False
    skip_frags = ["Oficiáln", "Prepočítan", "2023_", "2022_", "2024_",
                  "Anketa", "Hodnotenie", "účasť"]
    return not any(k in s for k in skip_frags)


def _parse_iv2_g(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV2_g"
    name = "podiel študentov, ktorí sa zapojili do hodnotenia kvality vzdelávania"
    cat = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    records: List[Dict] = []

    end_row = _find_next_indicator(df, row_idx + 1)

    oficialny_row: Optional[int] = None
    for ri in range(row_idx + 1, end_row):
        c1 = str(df.iloc[ri, 1]).strip() if pd.notna(df.iloc[ri, 1]) else ""
        if c1 == "Oficiálne percentá z ankety:":
            oficialny_row = ri
            break
    realne_end = oficialny_row if oficialny_row else end_row

    r0 = df.iloc[row_idx]
    fei_r_akrok = _to_float(r0.iloc[2])
    if fei_r_akrok is not None:
        records.append(_base_record(year, AREAS[0], "ratio", code, name,
            fei_r_akrok, True, cat, sub_type="reálne", snapshot_type="ak.rok"))
    for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
        lbl = str(r0.iloc[lcol]).strip() if pd.notna(r0.iloc[lcol]) else ""
        if lbl == "účasť ak.rok":
            records.append(_base_record(year, area, "ratio", code, name,
                _to_float(r0.iloc[vcol]), True, cat,
                sub_type="reálne", snapshot_type="ak.rok"))

    if row_idx + 1 < realne_end:
        r1 = df.iloc[row_idx + 1]
        fei_r_zs = _to_float(r1.iloc[2])
        if fei_r_zs is not None:
            records.append(_base_record(year, AREAS[0], "ratio", code, name,
                fei_r_zs, True, cat, sub_type="reálne", snapshot_type="ZS"))
        for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
            lbl = str(r1.iloc[lcol]).strip() if pd.notna(r1.iloc[lcol]) else ""
            if lbl == "účasť ZS":
                records.append(_base_record(year, area, "ratio", code, name,
                    _to_float(r1.iloc[vcol]), True, cat,
                    sub_type="reálne", snapshot_type="ZS"))

    realne_ls_found = False
    for ri in range(row_idx + 2, realne_end):
        r = df.iloc[ri]
        c5_lbl = str(r.iloc[5]).strip() if pd.notna(r.iloc[5]) else ""

        if c5_lbl == "účasť LS":
            realne_ls_found = True
            fei_r_ls = _to_float(r.iloc[2])
            if fei_r_ls is not None:
                records.append(_base_record(year, AREAS[0], "ratio", code, name,
                    fei_r_ls, True, cat, sub_type="reálne", snapshot_type="LS"))
            for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
                lbl = str(r.iloc[lcol]).strip() if pd.notna(r.iloc[lcol]) else ""
                if lbl == "účasť LS":
                    records.append(_base_record(year, area, "ratio", code, name,
                        _to_float(r.iloc[vcol]), True, cat,
                        sub_type="reálne", snapshot_type="LS"))
            continue

        snap = "LS" if realne_ls_found else "ZS"
        for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if not _iv2_g_is_prog(prog_str):
                continue
            records.append(_base_record(year, area, "ratio", code, name,
                _to_float(r.iloc[vcol]), True, cat,
                program=prog_str, sub_type="reálne", snapshot_type=snap))

    if oficialny_row is None:
        return records

    r_of0 = df.iloc[oficialny_row]
    fei_of_akrok = _to_float(r_of0.iloc[2])
    if fei_of_akrok is not None:
        records.append(_base_record(year, AREAS[0], "ratio", code, name,
            fei_of_akrok, True, cat, sub_type="oficiálne", snapshot_type="ak.rok"))
    for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
        lbl = str(r_of0.iloc[lcol]).strip() if pd.notna(r_of0.iloc[lcol]) else ""
        if lbl == "účasť ak.rok":
            records.append(_base_record(year, area, "ratio", code, name,
                _to_float(r_of0.iloc[vcol]), True, cat,
                sub_type="oficiálne", snapshot_type="ak.rok"))

    if oficialny_row + 1 < end_row:
        r_of1 = df.iloc[oficialny_row + 1]
        fei_of_zs = _to_float(r_of1.iloc[2])
        if fei_of_zs is not None:
            records.append(_base_record(year, AREAS[0], "ratio", code, name,
                fei_of_zs, True, cat, sub_type="oficiálne", snapshot_type="ZS"))
        for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
            lbl = str(r_of1.iloc[lcol]).strip() if pd.notna(r_of1.iloc[lcol]) else ""
            if lbl == "účasť ZS":
                records.append(_base_record(year, area, "ratio", code, name,
                    _to_float(r_of1.iloc[vcol]), True, cat,
                    sub_type="oficiálne", snapshot_type="ZS"))

    oficialny_ls_found = False
    for ri in range(oficialny_row + 2, end_row):
        r = df.iloc[ri]
        c5_lbl = str(r.iloc[5]).strip() if pd.notna(r.iloc[5]) else ""

        if c5_lbl == "účasť LS":
            oficialny_ls_found = True
            fei_of_ls = _to_float(r.iloc[2])
            if fei_of_ls is not None:
                records.append(_base_record(year, AREAS[0], "ratio", code, name,
                    fei_of_ls, True, cat, sub_type="oficiálne", snapshot_type="LS"))
            for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
                lbl = str(r.iloc[lcol]).strip() if pd.notna(r.iloc[lcol]) else ""
                if lbl == "účasť LS":
                    records.append(_base_record(year, area, "ratio", code, name,
                        _to_float(r.iloc[vcol]), True, cat,
                        sub_type="oficiálne", snapshot_type="LS"))
            continue

        snap = "LS" if oficialny_ls_found else "ZS"
        for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if not _iv2_g_is_prog(prog_str):
                continue
            records.append(_base_record(year, area, "ratio", code, name,
                _to_float(r.iloc[vcol]), True, cat,
                program=prog_str, sub_type="oficiálne", snapshot_type=snap))

    return records



def _parse_iv2_h(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV2_h"
    name = "miera spokojnosti študentov s kvalitou výučby a učiteľov"
    cat = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    records: List[Dict] = []

    end_row = _find_next_indicator(df, row_idx + 1)

    PERIOD_LABELS = {
        "odpovede ak.rok": "ak.rok",
        "odpovede ZS":     "ZS",
        "odpovede LS":     "LS",
    }

    r0 = df.iloc[row_idx]
    fei_val = _to_float(r0.iloc[2])
    if fei_val is not None:
        records.append(_base_record(year, AREAS[0], "ratio", code, name,
            fei_val, True, cat, snapshot_type="ak.rok"))
    for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
        lbl = str(r0.iloc[lcol]).strip() if pd.notna(r0.iloc[lcol]) else ""
        period = PERIOD_LABELS.get(lbl)
        if period:
            records.append(_base_record(year, area, "ratio", code, name,
                _to_float(r0.iloc[vcol]), True, cat, snapshot_type=period))

    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        fei_val = _to_float(r.iloc[2])

        c5_lbl = str(r.iloc[5]).strip() if pd.notna(r.iloc[5]) else ""
        period = PERIOD_LABELS.get(c5_lbl)

        if period and period != "ak.rok":
            if fei_val is not None:
                records.append(_base_record(year, AREAS[0], "ratio", code, name,
                    fei_val, True, cat, snapshot_type=period))
            for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
                lbl = str(r.iloc[lcol]).strip() if pd.notna(r.iloc[lcol]) else ""
                p = PERIOD_LABELS.get(lbl)
                if p == period:
                    records.append(_base_record(year, area, "ratio", code, name,
                        _to_float(r.iloc[vcol]), True, cat, snapshot_type=p))

    return records

def _parse_iv2_i(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV2_i"
    name = "miera spokojnosti študentov so špecifickými potrebami"
    cat = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    records = []
    row = df.iloc[row_idx]
    val = _to_float(row.iloc[2])
    if val is not None:
        records.append(_base_record(year, AREAS[0], "ratio", code, name,
            val, True, cat))
    return records


def _parse_iv2_j(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV2_j"
    name = "počet podaných podnetov študentov"
    cat = "Čl. IV - 2 - Učenie sa, vyučovanie a hodnotenie orientované na študenta"
    records = []

    SUB_LABELS = {
        None: "spolu",
        "Podnety - študentský senát": "študentský senát",
        "Podnety - študijné oddelenie": "študijné oddelenie",
        "Podnety - študijní poradcovia": "študijní poradcovia",
    }

    end_row = _find_next_indicator(df, row_idx + 1)

    rows_to_parse = [row_idx]
    for ri in range(row_idx + 1, min(row_idx + 4, end_row)):
        rows_to_parse.append(ri)

    for ri in rows_to_parse:
        r = df.iloc[ri]
        c1 = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""
        sub = None
        for label_key, sub_val in SUB_LABELS.items():
            if label_key is None and ri == row_idx:
                sub = "spolu"
                break
            elif label_key and c1.startswith(label_key):
                sub = sub_val
                break
        if sub is None:
            continue
        for col, deg in [(2, "Bc"), (3, "Ing"), (4, "PhD")]:
            val = _to_float(r.iloc[col])
            records.append(_base_record(year, AREAS[0], deg, code, name,
                val, False, cat, sub_type=sub))
    return records

def _is_iv3a_prog(s: str) -> bool:
    if not s or len(s) > 40:
        return False
    skip = {"FEI", "Elektrotechnika", "Informatika", "ELE učitelia", "INF učitelia",
            "spolu", "prof", "doc", "OA", "PE a ApE na Ing spojené"}
    if s in skip:
        return False
    skip_frags = ["Asistent", "Lektor", "učitelia", "spojené"]
    return not any(k in s for k in skip_frags)


def _parse_iv3_a(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV3_a"
    name = "počty všetkých učiteľov na ŠP podľa vedecko-pedagogických hodností"
    cat = "Čl. IV - 3 - Učitelia"
    records = []
    end_row = _find_next_indicator(df, row_idx + 1)

    r0 = df.iloc[row_idx]
    records.append(_base_record(year, AREAS[0], "spolu", code, name,
        _to_float(r0.iloc[2]), False, cat, program=None, sub_type=None))
    records.append(_base_record(year, AREAS[1], "spolu", code, name,
        _to_float(r0.iloc[6]), False, cat, program=None, sub_type=None))
    records.append(_base_record(year, AREAS[2], "spolu", code, name,
        _to_float(r0.iloc[10]), False, cat, program=None, sub_type=None))

    if row_idx + 2 < end_row:
        r2 = df.iloc[row_idx + 2]
        for area, cols in [
            (AREAS[1], [(6, "prof"), (7, "doc"), (8, "OA")]),
            (AREAS[2], [(10, "prof"), (11, "doc"), (12, "OA")]),
        ]:
            for col, sub in cols:
                val = _to_float(r2.iloc[col] if col < len(r2) else None)
                records.append(_base_record(year, area, "spolu", code, name,
                    val, False, cat, program="spolu", sub_type=sub))

    for ri in range(row_idx + 3, end_row):
        r = df.iloc[ri]
        e_name_cell = r.iloc[5] if 5 < len(r) else None
        if pd.notna(e_name_cell):
            prog_str = str(e_name_cell).strip()
            if _is_iv3a_prog(prog_str):
                for col, sub in [(6, "prof"), (7, "doc"), (8, "OA")]:
                    val = _to_float(r.iloc[col] if col < len(r) else None)
                    records.append(_base_record(year, AREAS[1], "spolu", code, name,
                        val, False, cat, program=prog_str, sub_type=sub))

        i_name_cell = r.iloc[9] if 9 < len(r) else None
        if pd.notna(i_name_cell):
            prog_str = str(i_name_cell).strip()
            if prog_str == "KB":
                continue
            if prog_str == "INF":
                prog_str = "INF+KB"
            if _is_iv3a_prog(prog_str):
                for col, sub in [(10, "prof"), (11, "doc"), (12, "OA")]:
                    val = _to_float(r.iloc[col] if col < len(r) else None)
                    records.append(_base_record(year, AREAS[2], "spolu", code, name,
                        val, False, cat, program=prog_str, sub_type=sub))

    return records


def _parse_iv3_b(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV3_b"
    name = "počty samostatných výskumných pracovníkov na ŠP"
    cat = "Čl. IV - 3 - Učitelia"
    records = []

    row = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        val = _to_float(row.iloc[col] if col < len(row) else None)
        records.append(_base_record(year, area, "spolu", code, name,
            val, False, cat))
    return records




def _parse_iv3_c(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV3_c"
    name = "počet učiteľov s vedecko-pedagogickým titulom (prof., doc.)"
    cat = "Čl. IV - 3 - Učitelia"
    records = []
    end_row = _find_next_indicator(df, row_idx + 1)

    r0 = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        records.append(_base_record(year, area, "spolu", code, name,
            _to_float(r0.iloc[col] if col < len(r0) else None), False, cat))

    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if prog_str == "KB":
                continue
            if prog_str == "INF":
                prog_str = "INF+KB"
            if not _is_iv3a_prog(prog_str):
                continue
            val = _to_float(r.iloc[vcol] if vcol < len(r) else None)
            records.append(_base_record(year, area, "spolu", code, name,
                val, False, cat, program=prog_str))
    return records


def _parse_iv3_d(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV3_d"
    name = "podiel učiteľov s PhD./ArtD. (alebo ekvivalentom)"
    cat = "Čl. IV - 3 - Učitelia"
    records = []
    row = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        records.append(_base_record(year, area, "spolu", code, name,
            _to_float(row.iloc[col] if col < len(row) else None), True, cat))
    return records



def _parse_iv3_e(df: pd.DataFrame, row_idx: int, year: int) -> List[Dict]:
    code = "IV3_e"
    name = "vek učiteľov ŠP zabezpečujúcich profilové predmety"
    cat = "Čl. IV - 3 - Učitelia"
    records = []
    end_row = _find_next_indicator(df, row_idx + 1)

    r0 = df.iloc[row_idx]
    for area, cols in [
        (AREAS[0], [(2, "priemer"), (3, "od"), (4, "do")]),
        (AREAS[1], [(6, "priemer"), (7, "od"), (8, "do")]),
        (AREAS[2], [(10, "priemer"), (11, "od"), (12, "do")]),
    ]:
        for col, sub in cols:
            val = _to_float(r0.iloc[col] if col < len(r0) else None)
            records.append(_base_record(year, area, "spolu", code, name,
                val, False, cat, program=None, sub_type=sub))

    for ri in range(row_idx + 2, end_row):
        r = df.iloc[ri]
        e_name = r.iloc[5] if 5 < len(r) else None
        if pd.notna(e_name):
            prog_str = str(e_name).strip()
            if _is_iv3a_prog(prog_str):
                for col, sub in [(6, "priemer"), (7, "od"), (8, "do")]:
                    val = _to_float(r.iloc[col] if col < len(r) else None)
                    records.append(_base_record(year, AREAS[1], "spolu", code, name,
                        val, False, cat, program=prog_str, sub_type=sub))
        i_name = r.iloc[9] if 9 < len(r) else None
        if pd.notna(i_name):
            prog_str = str(i_name).strip()
            if prog_str == "KB":
                continue
            if prog_str == "INF":
                prog_str = "INF+KB"
            if _is_iv3a_prog(prog_str):
                for col, sub in [(10, "priemer"), (11, "od"), (12, "do")]:
                    val = _to_float(r.iloc[col] if col < len(r) else None)
                    records.append(_base_record(year, AREAS[2], "spolu", code, name,
                        val, False, cat, program=prog_str, sub_type=sub))
    return records



def _parse_iv3_fgh(df: pd.DataFrame, row_idx: int, year: int,
                   code: str, name: str) -> list:
    cat = "Čl. IV - 3 - Učitelia"
    records = []
    end_row = _find_next_indicator(df, row_idx + 1)

    r0 = df.iloc[row_idx]
    for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
        records.append(_base_record(year, area, "spolu", code, name,
            _to_float(r0.iloc[col] if col < len(r0) else None), True, cat))

    for ri in range(row_idx + 1, end_row):
        r = df.iloc[ri]
        for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
            prog_cell = r.iloc[lcol] if lcol < len(r) else None
            if not pd.notna(prog_cell):
                continue
            prog_str = str(prog_cell).strip()
            if prog_str == "KB":
                continue
            if prog_str == "INF":
                prog_str = "INF+KB"
            if not _is_iv3a_prog(prog_str):
                continue
            val_cell = r.iloc[vcol] if vcol < len(r) else None
            if isinstance(val_cell, str) and val_cell.startswith("#"):
                val_cell = None
            records.append(_base_record(year, area, "spolu", code, name,
                _to_float(val_cell), True, cat, program=prog_str))
    return records


def _parse_iv3_f(df: pd.DataFrame, row_idx: int, year: int) -> list:
    return _parse_iv3_fgh(df, row_idx, year,
        "IV3_f", "podiel učiteľov – absolventov fakulty")


def _parse_iv3_g(df: pd.DataFrame, row_idx: int, year: int) -> list:
    return _parse_iv3_fgh(df, row_idx, year,
        "IV3_g", "podiel učiteľov, ktorí sú zároveň výskumnými pracovníkmi")


def _parse_iv3_h(df: pd.DataFrame, row_idx: int, year: int) -> list:
    return _parse_iv3_fgh(df, row_idx, year,
        "IV3_h", "podiel učiteľov s praxou v relevantnej oblasti mimo akademickej sféry")



def _parse_iv3_i(df: pd.DataFrame, row_idx: int, year: int) -> list:
    code = "IV3_i"
    name = "počet prijatých učiteľov zo zahraničia alebo iných VŠ"
    cat = "Čl. IV - 3 - Učitelia"
    row = df.iloc[row_idx]
    return [
        _base_record(year, AREAS[0], "spolu", code, name,
            _to_float(row.iloc[2]), False, cat),
        _base_record(year, AREAS[1], "spolu", code, name,
            _to_float(row.iloc[6]), False, cat),
        _base_record(year, AREAS[2], "spolu", code, name,
            _to_float(row.iloc[10]), False, cat),
    ]


def _parse_iv3_j(df: pd.DataFrame, row_idx: int, year: int) -> list:
    code = "IV3_j"
    name = "podiel vyslaných učiteľov / pomocné počty"
    cat = "Čl. IV - 3 - Učitelia"
    records = []
    end_row = _find_next_indicator(df, row_idx + 1)

    def safe_val(cell):
        if isinstance(cell, str) and cell.startswith("#"):
            return None
        return _to_float(cell)

    def parse_block(r0_idx, sub, is_pct):
        r0 = df.iloc[r0_idx]
        for area, col in [(AREAS[0], 2), (AREAS[1], 6), (AREAS[2], 10)]:
            records.append(_base_record(year, area, "spolu", code, name,
                safe_val(r0.iloc[col] if col < len(r0) else None), is_pct, cat,
                sub_type=sub))
        block_end = end_row
        for ri in range(r0_idx + 1, end_row):
            r = df.iloc[ri]
            c1 = str(r.iloc[1]).strip() if pd.notna(r.iloc[1]) else ""
            c0 = str(r.iloc[0]).strip() if pd.notna(r.iloc[0]) else ""
            if c1.startswith("pomocné") or (c0 not in ("", "nan") and ri > r0_idx):
                block_end = ri
                break
        for ri in range(r0_idx + 1, block_end):
            r = df.iloc[ri]
            for area, lcol, vcol in [(AREAS[1], 5, 6), (AREAS[2], 9, 10)]:
                prog_cell = r.iloc[lcol] if lcol < len(r) else None
                if not pd.notna(prog_cell):
                    continue
                prog_str = str(prog_cell).strip()
                if prog_str == "KB":
                    continue
                if prog_str == "INF":
                    prog_str = "INF+KB"
                skip = {"vyslaní / všetci", "súčet", "FEI", "Elektrotechnika", "Informatika",
                        "PE a ApE na Ing spojené"}
                if prog_str in skip or not prog_str:
                    continue
                val_cell = r.iloc[vcol] if vcol < len(r) else None
                records.append(_base_record(year, area, "spolu", code, name,
                    safe_val(val_cell), is_pct, cat,
                    program=prog_str, sub_type=sub))

    parse_block(row_idx, "vyslaní", True)

    for ri in range(row_idx + 1, end_row):
        c1 = str(df.iloc[ri, 1]).strip() if pd.notna(df.iloc[ri, 1]) else ""
        if c1.startswith("pomocné"):
            parse_block(ri, "súčet", False)
            break

    return records


class FEIParserII_ABC:
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

        row_indices_2: Dict[str, int] = {}
        in_section_2 = False
        for i, row in df.iterrows():
            c0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if c0 == "2":
                in_section_2 = True
                continue
            if in_section_2 and c0.isdigit() and c0 not in ("2",):
                in_section_2 = False
            if in_section_2 and c0 in "abcdefghij" and len(c0) == 1:
                if c0 not in row_indices_2:
                    row_indices_2[c0] = i

        row_indices_3: Dict[str, int] = {}
        in_section_3 = False
        for i, row in df.iterrows():
            c0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            if c0 == "3":
                in_section_3 = True
                continue
            if in_section_3 and c0.isdigit() and c0 not in ("3",):
                break
            if in_section_3 and c0 in "abcdefghij" and len(c0) == 1:
                if c0 not in row_indices_3:
                    row_indices_3[c0] = i

        row_indices = row_indices_2

        if "a" in row_indices_2:
            all_records.extend(_parse_iv2_a(df, row_indices_2["a"], year))
        if "b" in row_indices_2:
            all_records.extend(_parse_iv2_b(df, row_indices_2["b"], year))
        if "c" in row_indices_2:
            all_records.extend(_parse_iv2_c(df, row_indices_2["c"], year))
        if "d" in row_indices_2:
            all_records.extend(_parse_iv2_d(df, row_indices_2["d"], year))
        if "e" in row_indices_2:
            all_records.extend(_parse_iv2_e(df, row_indices_2["e"], year))
        if "f" in row_indices_2:
            all_records.extend(_parse_iv2_f(df, row_indices_2["f"], year))
        if "g" in row_indices_2:
            all_records.extend(_parse_iv2_g(df, row_indices_2["g"], year))
        if "h" in row_indices_2:
            all_records.extend(_parse_iv2_h(df, row_indices_2["h"], year))
        if "i" in row_indices_2:
            all_records.extend(_parse_iv2_i(df, row_indices_2["i"], year))
        if "j" in row_indices_2:
            all_records.extend(_parse_iv2_j(df, row_indices_2["j"], year))

        # Section 3
        if "a" in row_indices_3:
            all_records.extend(_parse_iv3_a(df, row_indices_3["a"], year))
        if "b" in row_indices_3:
            all_records.extend(_parse_iv3_b(df, row_indices_3["b"], year))
        if "c" in row_indices_3:
            all_records.extend(_parse_iv3_c(df, row_indices_3["c"], year))
        if "d" in row_indices_3:
            all_records.extend(_parse_iv3_d(df, row_indices_3["d"], year))
        if "e" in row_indices_3:
            all_records.extend(_parse_iv3_e(df, row_indices_3["e"], year))
        if "f" in row_indices_3:
            all_records.extend(_parse_iv3_f(df, row_indices_3["f"], year))
        if "g" in row_indices_3:
            all_records.extend(_parse_iv3_g(df, row_indices_3["g"], year))
        if "h" in row_indices_3:
            all_records.extend(_parse_iv3_h(df, row_indices_3["h"], year))
        if "i" in row_indices_3:
            all_records.extend(_parse_iv3_i(df, row_indices_3["i"], year))
        if "j" in row_indices_3:
            all_records.extend(_parse_iv3_j(df, row_indices_3["j"], year))

        return pd.DataFrame(all_records) if all_records else pd.DataFrame()