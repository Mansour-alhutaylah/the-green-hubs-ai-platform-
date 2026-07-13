"""Unit tests for ``normalize_text`` -- pure function, no I/O, no network."""

from app.infrastructure.documents.normalizer import normalize_text


def test_crlf_converted_to_lf() -> None:
    assert normalize_text("line one\r\nline two") == "line one\nline two"


def test_lone_cr_converted_to_lf() -> None:
    assert normalize_text("line one\rline two") == "line one\nline two"


def test_control_characters_removed_but_newline_and_tab_preserved() -> None:
    result = normalize_text("col1\tcol2\x00\x01\x02\nline two")
    assert result == "col1\tcol2\nline two"


def test_del_character_removed() -> None:
    assert normalize_text("abc\x7fdef") == "abcdef"


def test_trailing_whitespace_trimmed_per_line() -> None:
    result = normalize_text("line one   \nline two\t\t\n")
    assert result == "line one\nline two"


def test_excessive_blank_lines_collapsed_to_one() -> None:
    result = normalize_text("paragraph one\n\n\n\n\nparagraph two")
    assert result == "paragraph one\n\nparagraph two"


def test_single_blank_line_preserved() -> None:
    result = normalize_text("paragraph one\n\nparagraph two")
    assert result == "paragraph one\n\nparagraph two"


def test_leading_and_trailing_whitespace_trimmed() -> None:
    assert normalize_text("   \n\nsome text\n\n   ") == "some text"


def test_empty_string_returns_empty_string() -> None:
    assert normalize_text("") == ""


def test_whitespace_only_returns_empty_string() -> None:
    assert normalize_text("   \n\t\n   ") == ""


# ---------------------------------------------------------------------------
# Conservatism: content that must never change
# ---------------------------------------------------------------------------


def test_numbers_are_not_altered() -> None:
    text = "Revenue increased by 12345.6789 units in Q3."
    assert "12345.6789" in normalize_text(text)


def test_decimal_points_are_not_altered() -> None:
    text = "The ratio was 3.14159 exactly."
    assert "3.14159" in normalize_text(text)


def test_currency_values_are_not_altered() -> None:
    text = "Total cost: $1,234,567.89 USD."
    assert "$1,234,567.89" in normalize_text(text)


def test_measurement_units_are_not_altered() -> None:
    text = "Emissions were 45.2 kg CO2e per unit, measured at 20.5 degC."
    normalized = normalize_text(text)
    assert "45.2 kg CO2e" in normalized
    assert "20.5 degC" in normalized


def test_dates_are_not_altered() -> None:
    text = "Reported on 2026-07-13 and again on 07/13/2026."
    normalized = normalize_text(text)
    assert "2026-07-13" in normalized
    assert "07/13/2026" in normalized


def test_table_rows_are_preserved() -> None:
    text = "Metric\tValue\tUnit\nScope 1\t120.5\ttCO2e\nScope 2\t45.0\ttCO2e"
    normalized = normalize_text(text)
    assert "Metric\tValue\tUnit" in normalized
    assert "Scope 1\t120.5\ttCO2e" in normalized
    assert "Scope 2\t45.0\ttCO2e" in normalized


def test_headings_are_preserved() -> None:
    text = "1. Executive Summary\n\nSome content here.\n\n2. Methodology"
    normalized = normalize_text(text)
    assert "1. Executive Summary" in normalized
    assert "2. Methodology" in normalized


def test_page_markers_are_preserved() -> None:
    text = "Page 1 of 10\n\nSome content.\n\nPage 2 of 10"
    normalized = normalize_text(text)
    assert "Page 1 of 10" in normalized
    assert "Page 2 of 10" in normalized


def test_words_are_never_merged_across_lines() -> None:
    text = "This is one\nsentence split across lines."
    normalized = normalize_text(text)
    # Words must stay distinguishable -- no accidental concatenation like
    # "onesentence".
    assert "onesentence" not in normalized
    assert "one\nsentence" in normalized
