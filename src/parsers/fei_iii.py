import pandas as pd
from typing import Dict, List
from io import BytesIO


class FEIParser:
    def detect_bytes(self, content: bytes) -> bool:
        try:
            xls = pd.ExcelFile(BytesIO(content))
            return "Ukazovatele - čísla" in xls.sheet_names
        except Exception:
            return False

    def parse_bytes(self, content: bytes, year: int) -> pd.DataFrame:
        df_raw = pd.read_excel(BytesIO(content), sheet_name="Ukazovatele - čísla")
        return self._parse_df(df_raw, year)

    @staticmethod
    def _to_float(value):
        if pd.isna(value):
            return None
        s = str(value).strip()
        if s in ["-", ".", "", "#####", "######"]:
            return None
        try:
            return float(value)
        except Exception:
            try:
                return float(s.replace(",", "."))
            except Exception:
                return None

    def _parse_program_level_data(
        self,
        df_raw: pd.DataFrame,
        start_row: int,
        indicator_code: str,
        year: int,
        indicator_name: str,
    ) -> List[Dict]:
        program_data: List[Dict] = []
        is_percentage = indicator_code in ["b", "d", "g", "h"]

        current_row = start_row + 1
        max_rows_to_check = 20

        skip_keywords = [
            "ŠP v MAIS",
            "neotvorené / ponúkané",
            "zapísaní",
            "uchádzači",
            "všetci 1r",
            "všetci 2r",
            "všetci 3r",
            "všetci 4r",
            "všetci 5r",
            "vylúčenie",
            "zanechanie",
            "zmena ŠP",
            "Čísla Bc",
            "Čísla PhD",
            "Detaily po",
            "ukončení",
            "zapísaní",
            "en / všetci",
            "zahraniční",
            "iní prijatí",
            "všetci prij",
            "neotvorené",
            "ponúkané",
        ]

        for i in range(current_row, min(current_row + max_rows_to_check, len(df_raw))):
            first_col = df_raw.iloc[i, 0]

            if pd.notna(first_col):
                first_col_str = str(first_col).strip()
                if first_col_str in ["a", "b", "c", "d", "e", "f", "g", "h"]:
                    if first_col_str != indicator_code:
                        break
                if first_col_str.startswith("Čl."):
                    break

            program_name_ele = df_raw.iloc[i, 5] if 5 < len(df_raw.columns) else None
            if pd.notna(program_name_ele):
                program_str = str(program_name_ele).strip()
                is_valid = (
                    program_str
                    and program_str not in ["-", ".", "", " "]
                    and not any(keyword in program_str for keyword in skip_keywords)
                    and len(program_str) < 50
                )
                if is_valid:
                    for degree_offset, degree in enumerate(["Bc", "Ing", "PhD"]):
                        col_idx = 6 + degree_offset
                        value = df_raw.iloc[i, col_idx] if col_idx < len(df_raw.columns) else None
                        program_data.append(
                            {
                                "year": year,
                                "year_display": f"{year}-{year+1}",
                                "faculty": "FEI",
                                "area": "Elektrotechnika",
                                "area_type": "area",
                                "degree": degree,
                                "indicator_code": indicator_code,
                                "indicator_name": indicator_name,
                                "value": self._to_float(value),
                                "is_percentage": is_percentage,
                                "category": "Čl. III - Ukazovatele vstupu",
                                "program": program_str,
                            }
                        )

            program_name_inf = df_raw.iloc[i, 9] if 9 < len(df_raw.columns) else None
            if pd.notna(program_name_inf):
                program_str = str(program_name_inf).strip()
                is_valid = (
                    program_str
                    and program_str not in ["-", ".", "", " "]
                    and not any(keyword in program_str for keyword in skip_keywords)
                    and len(program_str) < 50
                )
                if is_valid:
                    for degree_offset, degree in enumerate(["Bc", "Ing", "PhD"]):
                        col_idx = 10 + degree_offset
                        value = df_raw.iloc[i, col_idx] if col_idx < len(df_raw.columns) else None
                        program_data.append(
                            {
                                "year": year,
                                "year_display": f"{year}-{year+1}",
                                "faculty": "FEI",
                                "area": "Informatika",
                                "area_type": "area",
                                "degree": degree,
                                "indicator_code": indicator_code,
                                "indicator_name": indicator_name,
                                "value": self._to_float(value),
                                "is_percentage": is_percentage,
                                "category": "Čl. III - Ukazovatele vstupu",
                                "program": program_str,
                            }
                        )

        return program_data

    def _parse_df(self, df_raw: pd.DataFrame, year: int) -> pd.DataFrame:
        areas = [
            {"name": "FEI", "col_idx": 2, "type": "faculty"},
            {"name": "Elektrotechnika", "col_idx": 6, "type": "area"},
            {"name": "Informatika", "col_idx": 10, "type": "area"},
        ]

        indicators = {
            "a": "počet ponúkaných ŠP podľa 1., 2., 3. stupňa vzdelávania",
            "b": "podiel neotvorených ŠP v akademickom roku z celkovej ponuky",
            "c": "počet ponúkaných ŠP v inom ako slovenskom jazyku",
            "d": "podiel neotvorených ŠP v inom ako slovenskom jazyku v akademickom roku z ich celkovej ponuky",
            "e": "počet uchádzačov o štúdium v príslušnom akademickom roku",
            "f": "počet uchádzačov o štúdium v príslušnom akademickom roku s iným ako slovenským občianstvom",
            "g": "podiel zapísaných študentov zo všetkých prihlásených záujemcov o štúdium v príslušnom akademickom roku",
            "h": "podiel prijatých študentov z iných vysokých škôl v 2. a 3. stupni vzdelávania",
        }

        all_data: List[Dict] = []

        for indicator_code, indicator_name in indicators.items():
            mask = df_raw.iloc[:, 0] == indicator_code
            if not mask.any():
                continue

            row_idx = mask.idxmax()
            is_percentage = indicator_code in ["b", "d", "g", "h"]

            # Area-level
            for area in areas:
                col_start = area["col_idx"]
                for degree_offset, degree in enumerate(["Bc", "Ing", "PhD"]):
                    col_idx = col_start + degree_offset
                    value = df_raw.iloc[row_idx, col_idx] if col_idx < len(df_raw.columns) else None

                    all_data.append(
                        {
                            "year": year,
                            "year_display": f"{year}-{year+1}",
                            "faculty": "FEI",
                            "area": area["name"],
                            "area_type": area["type"],
                            "degree": degree,
                            "indicator_code": indicator_code,
                            "indicator_name": indicator_name,
                            "value": self._to_float(value),
                            "is_percentage": is_percentage,
                            "category": "Čl. III - Ukazovatele vstupu",
                            "program": None,
                        }
                    )

            if indicator_code in ["e", "f", "g", "h"]:
                program_data = self._parse_program_level_data(
                    df_raw, row_idx, indicator_code, year, indicator_name
                )
                all_data.extend(program_data)

        return pd.DataFrame(all_data)