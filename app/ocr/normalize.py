import re
from typing import Any


_MULTI_SPACE_RE = re.compile(r"[^\S\n]{2,}")
_HYPHENATED_LINE_BREAK_RE = re.compile(r"(?<=[A-Za-z])-\s*\n\s*(?=[A-Za-z])")
_ORDERED_LIST_RE = re.compile(r"^\d+[.)]\s+")


def _default_normalization(normalized_text: str) -> dict[str, Any]:
    return {
        "normalized_text": normalized_text,
        "normalization": {
            "removed_blank_lines": 0,
            "collapsed_whitespace": False,
            "merged_broken_lines": False,
            "cleaned_hyphenation": False,
        },
    }


def _collapse_whitespace(text: str) -> tuple[str, bool]:
    changed = False
    normalized_lines: list[str] = []

    for line in text.split("\n"):
        collapsed = _MULTI_SPACE_RE.sub(" ", line.rstrip())
        if collapsed != line:
            changed = True
        normalized_lines.append(collapsed)

    return "\n".join(normalized_lines), changed


def _normalize_blank_lines(text: str) -> tuple[str, int]:
    removed_blank_lines = 0
    blank_run = 0
    normalized_lines: list[str] = []

    for line in text.split("\n"):
        if line == "":
            blank_run += 1
            if blank_run == 1:
                normalized_lines.append(line)
            else:
                removed_blank_lines += 1
            continue

        blank_run = 0
        normalized_lines.append(line)

    return "\n".join(normalized_lines), removed_blank_lines


def _looks_structural(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False

    if stripped.startswith(("- ", "* ", "• ", "|", "# ")):
        return True

    if _ORDERED_LIST_RE.match(stripped):
        return True

    if len(stripped) <= 80 and stripped.upper() == stripped and any(char.isalpha() for char in stripped):
        return True

    return False


def _should_merge_lines(current_line: str, next_line: str) -> bool:
    current = current_line.rstrip()
    following = next_line.lstrip()

    if not current or not following:
        return False

    if _looks_structural(current) or _looks_structural(following):
        return False

    if current.endswith((".", "!", "?", ":", ";")):
        return False

    return following[0].islower()


def _merge_broken_lines(text: str) -> tuple[str, bool]:
    lines = text.split("\n")
    if not lines:
        return text, False

    merged_lines = [lines[0]]
    merged_broken_lines = False

    for line in lines[1:]:
        if _should_merge_lines(merged_lines[-1], line):
            merged_lines[-1] = f"{merged_lines[-1].rstrip()} {line.lstrip()}"
            merged_broken_lines = True
            continue

        merged_lines.append(line)

    return "\n".join(merged_lines), merged_broken_lines


def normalize_ocr_text(text: str) -> dict[str, Any]:
    raw_text = text if isinstance(text, str) else ""
    normalized_text = raw_text.replace("\r\n", "\n").replace("\r", "\n").strip()

    if not normalized_text:
        return _default_normalization(normalized_text)

    dehyphenated_text = _HYPHENATED_LINE_BREAK_RE.sub("", normalized_text)
    cleaned_hyphenation = dehyphenated_text != normalized_text

    collapsed_text, collapsed_whitespace = _collapse_whitespace(dehyphenated_text)
    compacted_text, removed_blank_lines = _normalize_blank_lines(collapsed_text)
    merged_text, merged_broken_lines = _merge_broken_lines(compacted_text)

    return {
        "normalized_text": merged_text.strip(),
        "normalization": {
            "removed_blank_lines": removed_blank_lines,
            "collapsed_whitespace": collapsed_whitespace,
            "merged_broken_lines": merged_broken_lines,
            "cleaned_hyphenation": cleaned_hyphenation,
        },
    }


def normalize_ocr_result(result: dict[str, Any]) -> dict[str, Any]:
    text = result.get("text")
    safe_text = text if isinstance(text, str) else ""

    try:
        normalized = normalize_ocr_text(safe_text)
    except Exception:
        normalized = _default_normalization(safe_text.strip())

    return {
        **result,
        **normalized,
    }