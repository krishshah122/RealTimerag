from qdrant_client import QdrantClient

from config import QDRANT_API_KEY, QDRANT_HOST, QDRANT_PORT, QDRANT_URL


def create_qdrant_client() -> QdrantClient:
    if QDRANT_URL:
        return QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY or None,
            check_compatibility=False,
        )

    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        check_compatibility=False,
    )
