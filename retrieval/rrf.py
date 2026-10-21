from collections.abc import Iterable

from langsmith import traceable


@traceable(name="rrf_retriever")
def rrf_scores(dense: Iterable[dict], sparse: Iterable[tuple[str, float]], k: int = 60) -> list[tuple[str, float]]:
    """Return documents ordered by reciprocal-rank fusion score."""
    if k <= 0:
        raise ValueError("k must be greater than zero")

    scores: dict[str, float] = {}
    for results in (dense, sparse):
        seen: set[str] = set()
        for rank, result in enumerate(results):
            text = result["text"] if isinstance(result, dict) else result[0]
            if text in seen:
                continue
            seen.add(text)
            scores[text] = scores.get(text, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda item: item[1], reverse=True)


@traceable(name="rrf_retriever")
def rrf(dense: Iterable[dict], sparse: Iterable[tuple[str, float]], k: int = 60) -> list[str]:
    """Compatibility wrapper returning fused document texts."""
    return [text for text, _ in rrf_scores(dense, sparse, k)]
