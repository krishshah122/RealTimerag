def rrf(dense, sparse, k=60):
    scores = {}

    for rank, d in enumerate(dense):
        scores[d["text"]] = scores.get(d["text"], 0) + 1 / (k + rank)

    for rank, (text, _) in enumerate(sparse):
        scores[text] = scores.get(text, 0) + 1 / (k + rank)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [r[0] for r in ranked]
