import json

from stream.kafka_config import get_kafka_config

producer = None


def _get_producer():
    global producer
    if producer is None:
        from kafka import KafkaProducer

        producer = KafkaProducer(
            **get_kafka_config(),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
    return producer


def send_issue_event(event: dict):
    p = _get_producer()
    p.send("live_issues", event)
    p.flush()
