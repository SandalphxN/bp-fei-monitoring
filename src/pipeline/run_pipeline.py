from typing import Optional

import pandas as pd

from ..parsers.registry import get_parser_for_bytes
from ..storage.db import insert_upload, insert_records, delete_records_for_year
from ..utils.filename_year import infer_start_year_from_filename


def import_excel_to_db(
    content: bytes,
    filename: str,
    faculty: str,
    year: Optional[int] = None,
) -> int:
    inferred = infer_start_year_from_filename(filename)
    if year is None:
        if inferred is None:
            raise ValueError("Neviem určiť rok z názvu súboru. Zadaj rok manuálne.")
        year = inferred

    parsers = get_parser_for_bytes(content)

    frames = []
    for parser in parsers:
        try:
            df = parser.parse_bytes(content, int(year))
            if df is not None and not df.empty:
                frames.append(df)
        except Exception as e:
            print(f"[warn] Parser {parser.__class__.__name__} failed: {e}")

    if not frames:
        raise ValueError("Žiadny parser nevedel spracovať nahratý súbor.")

    combined = pd.concat(frames, ignore_index=True)

    delete_records_for_year(faculty=faculty, year=int(year))

    upload_id = insert_upload(
        faculty=faculty,
        year=int(year),
        filename=filename,
        content=content,
    )
    insert_records(upload_id, combined)
    return upload_id