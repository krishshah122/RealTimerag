from typing import TypedDict, List

class RAGState(TypedDict):
    query: str
    docs: List[str]
    answer: str
