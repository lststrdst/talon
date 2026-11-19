"""Replace these functions with calls to the project under test."""

import csv
from io import StringIO


def write_rows(rows: list[list[str]]) -> str:
    buffer = StringIO(newline="")
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue()


def read_rows(text: str) -> list[list[str]]:
    return list(csv.reader(StringIO(text, newline="")))
