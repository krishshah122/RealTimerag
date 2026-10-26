import unittest
from unittest.mock import patch

import numpy as np

from core.vector_backends.pinecone_backend import PineconeBackend, _pinecone_metadata


class PineconeBackendTests(unittest.TestCase):
    def test_metadata_is_flat_and_omits_nulls(self):
        result = _pinecone_metadata(
            "incident text",
            {
                "team_tag": "ops",
                "optional": None,
                "details": {"region": "west"},
                "labels": ["api", "urgent"],
            },
        )

        self.assertEqual(result["text"], "incident text")
        self.assertNotIn("optional", result)
        self.assertEqual(result["team_tag"], "ops")
        self.assertEqual(result["details"], '{"region": "west"}')
        self.assertEqual(result["labels"], ["api", "urgent"])

    def test_search_applies_metadata_filters_and_maps_matches(self):
        backend = PineconeBackend.__new__(PineconeBackend)
        backend.namespace = "incidents"

        class FakeIndex:
            def query(self, **kwargs):
                self.kwargs = kwargs
                return {
                    "matches": [
                        {
                            "score": 0.91,
                            "metadata": {
                                "text": "database alert",
                                "team_tag": "ops",
                            },
                        }
                    ]
                }

        backend.index = FakeIndex()
        with patch(
            "core.vector_backends.pinecone_backend.EmbeddingModel.encode",
            return_value=np.array([[0.1, 0.2]]),
        ):
            result = backend.search(
                "database",
                k=3,
                team_tag="ops",
                status="open",
                severity="HIGH",
            )

        self.assertEqual(result, [{
            "text": "database alert",
            "score": 0.91,
            "metadata": {"team_tag": "ops"},
        }])
        self.assertEqual(
            backend.index.kwargs["filter"],
            {
                "team_tag": {"$eq": "ops"},
                "status": {"$eq": "OPEN"},
                "severity": {"$eq": "high"},
            },
        )
        self.assertEqual(backend.index.kwargs["namespace"], "incidents")

    def test_delete_documents_deletes_matching_issue_id(self):
        backend = PineconeBackend.__new__(PineconeBackend)
        backend.namespace = "incidents"
        backend.all_docs = lambda: {
            "issue-1": {
                "text": "first incident",
                "metadata": {"issue_id": "issue-1"},
            },
            "issue-2": {
                "text": "second incident",
                "metadata": {"issue_id": "issue-2"},
            },
        }

        class FakeIndex:
            def delete(self, **kwargs):
                self.kwargs = kwargs

        backend.index = FakeIndex()
        deleted = backend.delete_documents(issue_id="issue-1")

        self.assertEqual(deleted, 1)
        self.assertEqual(
            backend.index.kwargs,
            {"ids": ["issue-1"], "namespace": "incidents"},
        )

    def test_all_docs_lists_pages_and_fetches_metadata(self):
        backend = PineconeBackend.__new__(PineconeBackend)
        backend.namespace = "incidents"

        class FakeIndex:
            def list(self, **kwargs):
                self.list_kwargs = kwargs
                return iter([{"vectors": [{"id": "issue-1"}]}])

            def fetch(self, **kwargs):
                self.fetch_kwargs = kwargs
                return {
                    "vectors": {
                        "issue-1": {
                            "metadata": {
                                "text": "database alert",
                                "team_tag": "ops",
                            }
                        }
                    }
                }

        backend.index = FakeIndex()
        documents = backend.all_docs()

        self.assertEqual(
            documents,
            {
                "issue-1": {
                    "text": "database alert",
                    "metadata": {"team_tag": "ops"},
                }
            },
        )
        self.assertEqual(backend.index.list_kwargs, {"namespace": "incidents", "limit": 100})
        self.assertEqual(
            backend.index.fetch_kwargs,
            {"ids": ["issue-1"], "namespace": "incidents"},
        )


if __name__ == "__main__":
    unittest.main()
