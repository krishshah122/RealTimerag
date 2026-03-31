from kafka import KafkaConsumer
import json
from core.vector_store import VectorStore

store = VectorStore()

consumer = KafkaConsumer(
    "live_issues",
    bootstrap_servers="localhost:9092",
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    auto_offset_reset="latest",
    enable_auto_commit=True
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
    metadata.setdefault("issue_type", event.get("type", "unknown"))
    metadata.setdefault("timestamp", event.get("timestamp"))
    metadata.setdefault("created_by_user_id", metadata.get("created_by_user_id"))
    metadata.setdefault("created_by_email", metadata.get("created_by_email"))

    store.add_document(text=event["text"], metadata=metadata)

    print("Stored in vector DB")
