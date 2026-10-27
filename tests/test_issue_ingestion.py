import asyncio
import os
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("GROQ_API_KEY", "test-key")

from fastapi import BackgroundTasks

from app.auth import UserContext
from app.issues import _ingest_issue


class IssueIngestionTests(unittest.TestCase):
    def test_ingest_publishes_without_waiting_for_summary_or_notification(self):
        user = UserContext(
            id="test-user",
            email="test@example.com",
            role="engineer",
            team="ops",
        )
        background_tasks = BackgroundTasks()
        incident = {
            "incident_id": "test-incident",
            "status": "OPEN",
            "severity": "medium",
            "team": "ops",
            "text": "Test incident",
        }

        with (
            patch("app.issues.IncidentManager.create", return_value=incident),
            patch("app.issues.correlate_on_ingest", return_value="CORR-test"),
            patch("app.issues.AnalyticsManager.track_issue"),
            patch(
                "app.issues.send_issue_event",
                return_value={
                    "topic": "live_issues",
                    "partition": 0,
                    "offset": 1,
                },
            ),
            patch("app.issues.summarize_incident", new_callable=AsyncMock) as summarize,
            patch("app.issues.notify_incident_created") as notify,
        ):
            result = asyncio.run(
                _ingest_issue(
                    {
                        "type": "alert",
                        "text": "Test incident",
                        "metadata": {"severity": "medium"},
                    },
                    user,
                    background_tasks,
                )
            )

        self.assertEqual(result["kafka_publish"]["status"], "published")
        self.assertEqual(result["summary_status"], "pending")
        self.assertEqual(len(background_tasks.tasks), 2)
        summarize.assert_not_awaited()
        notify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
