from typing import List, Optional, TypedDict


class RAGState(TypedDict, total=False):
    # Core query + answer fields
    query: str
    docs: List[str]
    answer: str

    # Team identifier used for multi-tenant retrieval / prompting
    team: Optional[str]
