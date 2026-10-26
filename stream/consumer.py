from kafka import KafkaConsumer
import json

from core.vector_store import VectorStore
from stream.kafka_config import get_kafka_config

store = VectorStore()

consumer = KafkaConsumer(
    "live_issues",
    **get_kafka_config(),
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    auto_offset_reset="latest",
    enable_auto_commit=True,
)

print("Kafka consumer started...")

for message in consumer:
    event = message.value
    print("Received:", event)

    metadata = event.get("metadata", {}) or {}
    team_tag = event.get("team_tag")
    if team_tag:
        metadata.setdefault("team_tag", team_tag)
    metadata.setdefault("issue_id", event.get("id"))
    metadata.setdefault("incident_id", event.get("id"))
    metadata.setdefault("issue_type", event.get("type", "unknown"))
    metadata.setdefault("timestamp", event.get("timestamp"))
    metadata.setdefault("status", metadata.get("status", "OPEN"))
    metadata.setdefault("severity", metadata.get("severity", "medium"))

    store.add_document(text=event["text"], metadata=metadata)
    print(
        f"Stored in {store.backend_name.capitalize()} "
        f"({len(metadata)} metadata fields)"
    )
