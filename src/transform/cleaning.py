from typing import Any, Optional

INVALID_TOKENS = {"-", ".", "", "#####", "######"}


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        s = str(value).strip()
    except Exception:
        return None

    if s in INVALID_TOKENS:
        return None

    try:
        return float(value)
    except Exception:
        try:
            s2 = s.replace(",", ".")
            return float(s2)
        except Exception:
            return None