import re
import unicodedata


def fold_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )


def normalize_for_fuzzy_match(value: str) -> str:
    folded = fold_accents(value.strip().lower())
    folded = re.sub(r"\s+", " ", folded)
    return re.sub(r"[^a-z0-9\s']+", "", folded)


def score_fuzzy_match(query: str, candidate: str) -> int:
    query_normalized = normalize_for_fuzzy_match(query)
    candidate_normalized = normalize_for_fuzzy_match(candidate)
    if not query_normalized:
        return -1

    if query_normalized == candidate_normalized:
        return 200

    if candidate_normalized.startswith(query_normalized):
        return 100 - (len(candidate_normalized) - len(query_normalized))

    if query_normalized in candidate_normalized:
        return 50 - (len(candidate_normalized) - len(query_normalized))

    query_index = 0
    for char in candidate_normalized:
        if query_index < len(query_normalized) and char == query_normalized[query_index]:
            query_index += 1
    if query_index == len(query_normalized):
        return 10

    return -1
