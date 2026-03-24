import re
from typing import Optional


def infer_start_year_from_filename(filename: str) -> Optional[int]:
    name = filename.strip()

    m = re.search(r"(20\d{2})\s*[-_]\s*(20\d{2})", name)
    if m:
        return int(m.group(1))

    m = re.search(r"(\d{2})\s*[-_]\s*(\d{2})", name)
    if m:
        y1 = int(m.group(1))
        return 2000 + y1

    return None