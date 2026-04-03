def chunk_for_retrieval(
    text: str,
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[str]:
    if not text or not text.strip():
        return []

    paragraphs = text.split("\n\n")
    merged: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            continue

        para_len = len(stripped)

        if current and current_len + para_len + 1 > max_chars:
            merged.append("\n\n".join(current))
            overlap_text = "\n\n".join(current)
            if overlap_chars > 0 and len(overlap_text) > overlap_chars:
                tail = overlap_text[-overlap_chars:]
                boundary = tail.find("\n\n")
                if boundary != -1:
                    tail = tail[boundary + 2:]
                current = [tail] if tail.strip() else []
                current_len = len(tail) if tail.strip() else 0
            else:
                current = []
                current_len = 0
        if current:
            current.append(stripped)
            current_len += para_len + 1
        else:
            current = [stripped]
            current_len = para_len

    if current:
        candidate = "\n\n".join(current)
        if merged and len(candidate) < 80 and len(merged[-1]) + len(candidate) + 2 <= max_chars * 1.2:
            merged[-1] = merged[-1] + "\n\n" + candidate
        else:
            merged.append(candidate)

    return merged
