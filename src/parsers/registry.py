from .fei_iii import FEIParser
from .fei_iv import FEIParserIV_ABC, FEIParserII_ABC
from .fei_v import FEIParserV_ABC

PARSERS = [
    FEIParser(),
    FEIParserIV_ABC(),
    FEIParserII_ABC(),
    FEIParserV_ABC(),
]


def get_parser_for_bytes(content: bytes):
    matched = [p for p in PARSERS if p.detect_bytes(content)]
    if not matched:
        raise ValueError("No suitable parser found for uploaded file.")
    return matched