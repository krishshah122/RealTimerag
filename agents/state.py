from typing import List, Optional, TypedDict


class RAGState(TypedDict, total=False):
    query: str
    docs: List[str]
    answer: str
    team: Optional[str]
    user_context: Optional[dict]
    status_filter: Optional[str]
    severity_filter: Optional[str]
    blocked_reason: Optional[str]
