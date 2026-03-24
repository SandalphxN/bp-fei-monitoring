import os
import re
import glob
from typing import List, Optional

from .paths import data_raw_dir


def get_available_years(data_folder: Optional[str] = None) -> List[int]:
    folder = data_folder or data_raw_dir()
    files = glob.glob(f"{folder}/*.xlsx")
    years: List[int] = []

    patterns = [
        r"(\d{4})-(\d{4})\.xlsx",
        r"(\d{2})-(\d{2})\.xlsx",
        r"(\d{2})_(\d{2})\.xlsx",
    ]

    for file in files:
        basename = os.path.basename(file)
        for pattern in patterns:
            match = re.match(pattern, basename)
            if match:
                year1 = int(match.group(1))
                year = 2000 + year1 if year1 < 100 else year1
                years.append(year)
                break

    return sorted(list(set(years)))


def find_excel_for_year(year: int, data_folder: Optional[str] = None) -> Optional[str]:
    folder = data_folder or data_raw_dir()
    candidates = [
        os.path.join(folder, f"{year}-{year + 1}.xlsx"),
        os.path.join(folder, f"{year - 2000}-{year - 2000 + 1}.xlsx"),
        os.path.join(folder, f"{year - 2000}_{year - 2000 + 1}.xlsx"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def format_year_display(year: int) -> str:
    return f"{year}-{year + 1}"