import pytest

from app.infrastructure.documents.chunker import chunk_text


def test_empty_document_returns_no_chunks() -> None:
    assert chunk_text("") == []


def test_whitespace_only_document_returns_no_chunks() -> None:
    assert chunk_text("   \n\t  ") == []


def test_small_document_returns_single_chunk() -> None:
    text = "Scope 1 emissions decreased by 12% year over year."

    chunks = chunk_text(text, chunk_size=500, chunk_overlap=50)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].text == text
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len(text)


def test_document_exactly_chunk_size_returns_single_chunk() -> None:
    text = "a" * 100

    chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)

    assert len(chunks) == 1
    assert chunks[0].text == text


def test_large_document_splits_into_multiple_chunks() -> None:
    paragraph = "Sustainability reporting requires accurate emissions data. " * 20
    text = "\n\n".join([paragraph] * 5)

    chunks = chunk_text(text, chunk_size=300, chunk_overlap=50)

    assert len(chunks) > 1
    assert all(len(c.text) <= 300 + 50 for c in chunks)  # allow boundary slack


def test_chunk_indices_are_sequential_and_ordered() -> None:
    text = "word " * 500

    chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunks_reconstruct_char_offsets_into_original_text() -> None:
    text = "word " * 500

    chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)

    for chunk in chunks:
        assert text[chunk.char_start : chunk.char_end] == chunk.text


def test_configurable_chunk_size_changes_chunk_count() -> None:
    text = "Emissions data point. " * 100

    small_chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
    large_chunks = chunk_text(text, chunk_size=1000, chunk_overlap=10)

    assert len(small_chunks) > len(large_chunks)


def test_configurable_overlap_repeats_trailing_context() -> None:
    text = "Alpha beta gamma delta epsilon zeta eta theta iota kappa. " * 30

    chunks = chunk_text(text, chunk_size=150, chunk_overlap=40)

    assert len(chunks) > 1
    # The tail of each chunk should reappear at the head of the next chunk's
    # source window (allowing for boundary snapping), proving overlap occurred.
    first_tail = chunks[0].text[-10:]
    assert first_tail in text[chunks[0].char_end - 40 - 10 : chunks[0].char_end + 10]


def test_prefers_paragraph_boundary_over_hard_cut() -> None:
    first = "A" * 90
    second = "B" * 90
    text = first + "\n\n" + second

    chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)

    assert chunks[0].text == first + "\n\n"


def test_no_chunk_splits_mid_word_when_space_available() -> None:
    text = " ".join(f"word{i}" for i in range(200))

    chunks = chunk_text(text, chunk_size=50, chunk_overlap=5)

    for chunk in chunks[:-1]:
        assert chunk.text.endswith(" ") or chunk.text.endswith("\n")


def test_chunk_size_must_be_positive() -> None:
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=0, chunk_overlap=0)


def test_chunk_overlap_must_be_non_negative() -> None:
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=100, chunk_overlap=-1)


def test_chunk_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError):
        chunk_text("some text", chunk_size=100, chunk_overlap=100)
