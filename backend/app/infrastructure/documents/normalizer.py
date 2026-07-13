"""Conservative text normalization for extracted document text.

Framework-agnostic, pure function -- no FastAPI, SQLAlchemy, or AI/RAG
imports. Deliberately minimal: only whitespace/control-character
cleanup that could never alter meaning. Numbers, decimal points,
currency values, units, dates, table rows, headings, and page markers
are never touched -- this is not a formatting or language tool, and it
never uses AI.
"""

_MAX_CONSECUTIVE_BLANK_LINES = 1  # runs of 2+ blank lines collapse to exactly one


def normalize_text(text: str) -> str:
    """Conservatively normalize extracted document text.

    Applies only:
        - CRLF/CR -> LF
        - removal of control characters that cannot represent useful
          text (keeps newline and tab; also strips DEL)
        - trailing whitespace trimmed per line
        - runs of 2+ consecutive blank lines collapsed to exactly one
        - leading/trailing whitespace trimmed from the complete text
    """
    unified = text.replace("\r\n", "\n").replace("\r", "\n")
    stripped_controls = "".join(
        ch for ch in unified if ch in ("\n", "\t") or (ord(ch) >= 0x20 and ch != "\x7f")
    )
    lines = [line.rstrip() for line in stripped_controls.split("\n")]

    collapsed: list[str] = []
    blank_run = 0
    for line in lines:
        if line == "":
            blank_run += 1
            if blank_run <= _MAX_CONSECUTIVE_BLANK_LINES:
                collapsed.append(line)
        else:
            blank_run = 0
            collapsed.append(line)

    return "\n".join(collapsed).strip()
