import json
import threading

from stream.kafka_config import get_issue_topic, get_kafka_config

producer = None
producer_lock = threading.Lock()


def _get_producer():
    global producer
    if producer is None:
        with producer_lock:
            if producer is None:
                from kafka import KafkaProducer

                producer = KafkaProducer(
                    **get_kafka_config(),
                    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                )
    return producer


def send_issue_event(event: dict):
    p = _get_producer()
    future = p.send(get_issue_topic(), event)
    metadata = future.get(timeout=10)
    return {
        "topic": metadata.topic,
        "partition": metadata.partition,
        "offset": metadata.offset,
    }
