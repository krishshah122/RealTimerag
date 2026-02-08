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
    
    for d in docs:
        # Clean the document text before splitting
        doc_words = set(clean_text(d["text"]).split())
        
        # Calculate overlap
        overlap = len(query_words & doc_words)
        scored.append((overlap, d))
    
    # Sort by overlap score in descending order
    scored.sort(reverse=True, key=lambda x: x[0])
    
    return [d for _, d in scored]