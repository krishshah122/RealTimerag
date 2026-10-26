"""Shared Kafka client configuration for local and hosted brokers."""

import os

from dotenv import load_dotenv


load_dotenv()


def get_kafka_config() -> dict:
    """Build Kafka client options without logging credentials."""
    bootstrap_servers = (
        os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        or os.getenv("bootstrap_kafka_url")
        or "localhost:9092"
    )
    config = {
        "bootstrap_servers": [
            server.strip() for server in bootstrap_servers.split(",") if server.strip()
        ],
    }

    security_protocol = (
        os.getenv("KAFKA_SECURITY_PROTOCOL")
        or os.getenv("SASL_PROTO")
        or ""
    ).strip()
    sasl_mechanism = (
        os.getenv("KAFKA_SASL_MECHANISM")
        or os.getenv("SASL_MECH")
        or ""
    ).strip()

    if security_protocol:
        config["security_protocol"] = security_protocol
    if sasl_mechanism:
        config["sasl_mechanism"] = sasl_mechanism

    if security_protocol.upper().startswith("SASL"):
        username = os.getenv("KAFKA_SASL_USERNAME") or os.getenv("SASL_USERNAME")
        password = os.getenv("KAFKA_SASL_PASSWORD") or os.getenv("SASL_PASSWORD")
        if not username or not password:
            raise RuntimeError(
                "Kafka SASL is enabled; set KAFKA_SASL_USERNAME and "
                "KAFKA_SASL_PASSWORD."
            )
        if not sasl_mechanism:
            raise RuntimeError(
                "Kafka SASL is enabled; set KAFKA_SASL_MECHANISM."
            )
        config["sasl_plain_username"] = username
        config["sasl_plain_password"] = password

    if not config["bootstrap_servers"]:
        raise RuntimeError("Set KAFKA_BOOTSTRAP_SERVERS to a Kafka broker address.")

    return config
