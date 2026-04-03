import re
from typing import Any


_DELIMITER_RE = re.compile(r"[|]")
_COLUMN_GAP_RE = re.compile(r" {3,}")
_TITLE_COLON_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 ,&/-]{0,78}:\s*$")


def _empty_structure() -> dict[str, Any]:
    return {
        "sections": [],
        "paragraphs": [],
        "lines": [],
        "table_candidates": [],
    }


def _is_section_title(line: str, next_line: str | None) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if _looks_like_table_row(stripped):
        return False

    if _TITLE_COLON_RE.match(stripped):
        return True

    if (
        stripped == stripped.upper()
        and any(c.isalpha() for c in stripped)
        and len(stripped) <= 80
    ):
        return True

    if (
        next_line is not None
        and len(stripped) <= 60
        and stripped[0].isupper()
        and not stripped.endswith((".", ",", ";"))
        and len(next_line.strip()) > len(stripped)
    ):
        return True

    return False


def _looks_like_table_row(line: str) -> bool:
    if _DELIMITER_RE.search(line):
        return True

    gaps = _COLUMN_GAP_RE.findall(line)
    if len(gaps) >= 2 and len(line.strip()) > 10:
        return True

    return False


def _extract_table_candidates(lines: list[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    run: list[str] = []
    start_line = 0

    for idx, line in enumerate(lines):
        if _looks_like_table_row(line):
            if not run:
                start_line = idx
            run.append(line)
        else:
            if len(run) >= 2:
                candidates.append({
                    "start_line": start_line,
                    "end_line": start_line + len(run) - 1,
                    "row_count": len(run),
                    "raw_lines": run,
                })
            run = []

    if len(run) >= 2:
        candidates.append({
            "start_line": start_line,
            "end_line": start_line + len(run) - 1,
            "row_count": len(run),
            "raw_lines": run,
        })

    return candidates


def _build_paragraphs(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.strip():
            current.append(line)
        else:
            if current:
                paragraphs.append("\n".join(current))
                current = []

    if current:
        paragraphs.append("\n".join(current))

    return paragraphs


def _build_sections(lines: list[str]) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    current_title: str | None = None
    content_lines: list[str] = []

    for idx, line in enumerate(lines):
        next_line = lines[idx + 1] if idx + 1 < len(lines) else None
        if _is_section_title(line, next_line):
            if current_title is not None:
                sections.append({
                    "title": current_title,
                    "content": "\n".join(content_lines).strip(),
                })
            current_title = line.strip().rstrip(":")
            content_lines = []
        elif current_title is not None:
            content_lines.append(line)

    if current_title is not None:
        sections.append({
            "title": current_title,
            "content": "\n".join(content_lines).strip(),
        })

    return sections


def structure_ocr_output(normalized_text: str) -> dict[str, Any]:
    safe_text = normalized_text if isinstance(normalized_text, str) else ""
    stripped = safe_text.strip()

    if not stripped:
        return _empty_structure()

    all_lines = stripped.split("\n")
    non_empty_lines = [line for line in all_lines if line.strip()]

    try:
        sections = _build_sections(non_empty_lines)
    except Exception:
        sections = []

    try:
        paragraphs = _build_paragraphs(all_lines)
    except Exception:
        paragraphs = []

    try:
        table_candidates = _extract_table_candidates(non_empty_lines)
    except Exception:
        table_candidates = []

    return {
        "sections": sections,
        "paragraphs": paragraphs,
        "lines": non_empty_lines,
        "table_candidates": table_candidates,
    }


def structure_ocr_result(result: dict[str, Any]) -> dict[str, Any]:
    normalized_text = result.get("normalized_text")
    safe_text = normalized_text if isinstance(normalized_text, str) else ""

    try:
        structured = structure_ocr_output(safe_text)
    except Exception:
        structured = _empty_structure()

    return {
        **result,
        "structured": structured,
    }
