import string
import re
from langsmith import traceable
def clean_text(text):

    text = text.lower()
    # 2. Remove punctuation using regex or string.punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    # 3. Optional: Remove extra whitespace
    return text.strip()

@traceable(name="reranking")
def simple_rerank(query, docs):
    query_words = set(clean_text(query).split())
    scored = []
    query_word_count = max(len(query_words), 1)

    for d in docs:
        doc_words = set(clean_text(d["text"]).split())
        overlap = len(query_words & doc_words)
        lexical_score = overlap / query_word_count
        retrieval_score = d.get("final_score", 0)
        scored.append((0.7 * retrieval_score + 0.3 * lexical_score, d))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [doc for _, doc in scored]
