import pandas as pd
from typing import Dict, Optional


class FacultyMetricsCalculator:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.metrics: Dict[str, Dict] = {}

    def get_value(self, indicator_code: str, area: Optional[str] = None, degree: Optional[str] = None) -> float:
        filtered = self.df[self.df["indicator_code"] == indicator_code]
        if area:
            filtered = filtered[filtered["area"] == area]
        if degree:
            filtered = filtered[filtered["degree"] == degree]

        if len(filtered) == 0:
            return 0.0

        total = filtered["value"].sum()
        return float(total) if pd.notna(total) else 0.0

    def calculate_admission_metrics(self) -> Dict:
        metrics: Dict[str, float] = {}

        metrics["total_programs"] = int(self.get_value("a"))
        metrics["unopened_programs_ratio"] = round(self.get_value("b"), 2)
        metrics["foreign_language_programs"] = int(self.get_value("c"))
        metrics["unopened_foreign_ratio"] = round(self.get_value("d"), 2)
        metrics["total_applicants"] = int(self.get_value("e"))
        metrics["foreign_applicants"] = int(self.get_value("f"))
        metrics["enrollment_rate"] = round(self.get_value("g"), 2)
        metrics["transfer_rate"] = round(self.get_value("h"), 2)

        if metrics["total_programs"] > 0:
            metrics["foreign_programs_ratio"] = round(
                (metrics["foreign_language_programs"] / metrics["total_programs"]) * 100, 2
            )
        else:
            metrics["foreign_programs_ratio"] = 0.0

        if metrics["total_applicants"] > 0:
            metrics["foreign_applicants_ratio"] = round(
                (metrics["foreign_applicants"] / metrics["total_applicants"]) * 100, 2
            )
        else:
            metrics["foreign_applicants_ratio"] = 0.0

        self.metrics["Ukazovatele vstupu (Čl. III)"] = metrics
        return metrics

    def calculate_all_metrics(self) -> Dict:
        self.calculate_admission_metrics()
        return self.metrics