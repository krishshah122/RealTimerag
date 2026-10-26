import unittest
from unittest.mock import patch

from stream.kafka_config import get_kafka_config


class KafkaConfigTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
