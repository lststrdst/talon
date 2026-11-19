import csv
from io import StringIO

from hypothesis import given, settings
from hypothesis import strategies as st

from csv_example import read_rows, write_rows


CELL = st.one_of(
    st.text(
        alphabet=st.characters(
            codec="utf-8",
            exclude_categories=("Cc",),
            include_characters=("\t", "\r", "\n"),
        ),
        max_size=16,
    ),
    st.sampled_from((",", '"', "\r", "\n", " ", "Привет", "東京", "東京東京", "📦", "e\u0301")),
)
ROWS = st.lists(st.lists(CELL, min_size=1, max_size=5), max_size=5)

EXAMPLE_ROWS = [['Привет, "мир"', "line\r\nbreak", " e\u0301 ", "📦", ""]]
EXAMPLE_CSV = '"Привет, ""мир""","line\r\nbreak", e\u0301 ,📦,\r\n'


@settings(max_examples=120, derandomize=True)
@given(rows=ROWS)
def test_csv_round_trip(rows):
    expected = [row.copy() for row in rows]
    reference = StringIO(newline="")
    csv.writer(reference, dialect="excel").writerows(expected)
    exported = write_rows(rows)
    decoded_export = list(csv.reader(StringIO(exported, newline=""), dialect="excel"))

    assert read_rows(exported) == expected, "Project round trip changed the rows"
    assert decoded_export == expected, "Standard reader saw different exported rows"
    assert read_rows(reference.getvalue()) == expected, "Project reader misread standard CSV"


def test_read_known_csv():
    assert read_rows(EXAMPLE_CSV) == EXAMPLE_ROWS


def test_write_known_rows():
    text = write_rows([row.copy() for row in EXAMPLE_ROWS])
    actual = list(csv.reader(StringIO(text, newline=""), dialect="excel"))
    assert actual == EXAMPLE_ROWS
