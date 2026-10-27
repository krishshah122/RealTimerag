import unittest
from unittest.mock import patch

from stream.kafka_config import (
    get_consumer_group_id,
    get_issue_topic,
    get_kafka_config,
)
from stream import producer


class KafkaConfigTests(unittest.TestCase):
    def test_issue_topic_defaults_and_can_be_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(get_issue_topic(), "live_issues")

        with patch.dict("os.environ", {"KAFKA_ISSUES_TOPIC": "live_issues_eval"}):
            self.assertEqual(get_issue_topic(), "live_issues_eval")

    def test_issue_topic_rejects_empty_value(self):
        with patch.dict("os.environ", {"KAFKA_ISSUES_TOPIC": "  "}):
            with self.assertRaisesRegex(RuntimeError, "must not be empty"):
                get_issue_topic()

    def test_consumer_group_defaults_and_can_be_configured(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(get_consumer_group_id(), "incident-vector-indexer")

        with patch.dict(
            "os.environ", {"KAFKA_CONSUMER_GROUP_ID": "incident-indexer-eval"}
        ):
            self.assertEqual(get_consumer_group_id(), "incident-indexer-eval")

    def test_reads_redpanda_sasl_ssl_settings(self):
        with patch.dict(
            "os.environ",
            {
                "bootstrap_kafka_url": "broker.example:9092",
                "SASL_PROTO": "SASL_SSL",
                "SASL_MECH": "SCRAM-SHA-256",
                "SASL_USERNAME": "demo-user",
                "SASL_PASSWORD": "demo-password",
            },
            clear=True,
        ):
            config = get_kafka_config()

        self.assertEqual(config["bootstrap_servers"], ["broker.example:9092"])
        self.assertEqual(config["security_protocol"], "SASL_SSL")
        self.assertEqual(config["sasl_mechanism"], "SCRAM-SHA-256")
        self.assertEqual(config["sasl_plain_username"], "demo-user")
        self.assertEqual(config["sasl_plain_password"], "demo-password")

    def test_prefers_deployment_variable_names(self):
        with patch.dict(
            "os.environ",
            {
                "KAFKA_BOOTSTRAP_SERVERS": "broker-a:9092, broker-b:9092",
                "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
                "KAFKA_SASL_MECHANISM": "SCRAM-SHA-256",
                "KAFKA_SASL_USERNAME": "deployment-user",
                "KAFKA_SASL_PASSWORD": "deployment-password",
            },
            clear=True,
        ):
            config = get_kafka_config()

        self.assertEqual(
            config["bootstrap_servers"], ["broker-a:9092", "broker-b:9092"]
        )
        self.assertEqual(config["sasl_plain_username"], "deployment-user")

    def test_requires_credentials_when_sasl_is_enabled(self):
        with patch.dict(
            "os.environ",
            {
                "KAFKA_BOOTSTRAP_SERVERS": "broker.example:9092",
                "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
                "KAFKA_SASL_MECHANISM": "SCRAM-SHA-256",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "KAFKA_SASL_USERNAME"):
                get_kafka_config()


class KafkaProducerTests(unittest.TestCase):
    def test_waits_for_broker_ack_and_returns_topic_partition_offset(self):
        class Metadata:
            topic = "live_issues_eval"
            partition = 2
            offset = 19

        class Future:
            def get(self, timeout):
                self.timeout = timeout
                return Metadata()

        class FakeProducer:
            def __init__(self):
                self.future = Future()
                self.sent = None

            def send(self, topic, event):
                self.sent = (topic, event)
                return self.future

        fake_producer = FakeProducer()
        with (
            patch.dict("os.environ", {"KAFKA_ISSUES_TOPIC": "live_issues_eval"}),
            patch.object(producer, "_get_producer", return_value=fake_producer),
        ):
            result = producer.send_issue_event({"id": "test-incident"})

        self.assertEqual(fake_producer.sent, ("live_issues_eval", {"id": "test-incident"}))
        self.assertEqual(fake_producer.future.timeout, 10)
        self.assertEqual(
            result,
            {"topic": "live_issues_eval", "partition": 2, "offset": 19},
        )


if __name__ == "__main__":
    unittest.main()
