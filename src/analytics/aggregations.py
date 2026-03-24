import pandas as pd


def pivot_data_by_area(df: pd.DataFrame, include_year: bool = False) -> pd.DataFrame:
    if include_year:
        pivot = (
            df.groupby(["year_display", "area", "indicator_code", "indicator_name"])
            .agg({"value": "sum", "is_percentage": "first"})
            .reset_index()
        )
        pivot = pivot.sort_values(["year_display", "area", "indicator_code"])
        return pivot

    pivot = (
        df.groupby(["area", "indicator_code", "indicator_name"])
        .agg({"value": "sum", "is_percentage": "first"})
        .reset_index()
    )

    area_order = {"FEI": 0, "Elektrotechnika": 1, "Informatika": 2}
    pivot["sort_order"] = pivot["area"].map(area_order).fillna(99)
    pivot = pivot.sort_values(["sort_order", "indicator_code"]).drop(columns=["sort_order"])
    return pivot


def get_programs_for_area(df: pd.DataFrame, area: str):
    if area in ("Všetky oblasti", "FEI"):
        return []
    programs = df[(df["area"] == area) & (df["program"].notna())]["program"].unique().tolist()
    return sorted(programs)