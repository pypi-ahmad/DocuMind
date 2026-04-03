def keyword_match_score(text: str, expected_keywords: list[str]) -> float:
    """Return fraction of expected keywords found in text (case-insensitive)."""
    if not expected_keywords:
        return 1.0
    lower_text = text.lower()
    matched = sum(1 for kw in expected_keywords if kw.lower() in lower_text)
    return matched / len(expected_keywords)


def hit_contains_expected(hits: list[dict], expected_ids: list[str]) -> float:
    """Return fraction of expected doc/chunk ids present in hit list."""
    if not expected_ids:
        return 1.0
    hit_ids: set[str] = set()
    for hit in hits:
        hit_ids.add(str(hit.get("doc_id", "")))
        hit_ids.add(str(hit.get("chunk_id", "")))
    matched = sum(1 for eid in expected_ids if eid in hit_ids)
    return matched / len(expected_ids)


def citation_contains_expected(citations: list[dict], expected_ids: list[str]) -> float:
    """Return fraction of expected ids present in citations."""
    if not expected_ids:
        return 1.0
    cit_ids: set[str] = set()
    for cit in citations:
        cit_ids.add(str(cit.get("doc_id", "")))
        cit_ids.add(str(cit.get("chunk_id", "")))
    matched = sum(1 for eid in expected_ids if eid in cit_ids)
    return matched / len(expected_ids)


def safe_average(values: list[float]) -> float:
    """Return arithmetic mean, or 0.0 for empty list."""
    if not values:
        return 0.0
    return sum(values) / len(values)
