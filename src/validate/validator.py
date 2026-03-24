from dataclasses import dataclass
from typing import List
import pandas as pd

from ..pipeline.schema import REQUIRED_COLUMNS


@dataclass
class ValidationReport:
    ok: bool
    errors: List[str]
    warnings: List[str]


def validate_df(df: pd.DataFrame) -> ValidationReport:
    errors: List[str] = []
    warnings: List[str] = []

    if df is None or df.empty:
        errors.append("Dataset je prázdny alebo None.")
        return ValidationReport(ok=False, errors=errors, warnings=warnings)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Chýbajúce stĺpce: {missing}")

    if "is_percentage" in df.columns and "value" in df.columns:
        perc = df[df["is_percentage"] == True]["value"].dropna()
        if not perc.empty:
            if (perc < 0).any() or (perc > 1.5).any():
                warnings.append("Našli sa percentuálne hodnoty mimo očakávaný rozsah (0..1). Skontroluj zdroj.")

    if "indicator_code" in df.columns:
        unique_codes = sorted(df["indicator_code"].dropna().unique().tolist())
        if len(unique_codes) == 0:
            warnings.append("Nenašli sa žiadne ukazovatele (indicator_code).")

    ok = len(errors) == 0
    return ValidationReport(ok=ok, errors=errors, warnings=warnings)