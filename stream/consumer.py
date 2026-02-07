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

    store.add_document(
        text=event["text"],
        metadata=event.get("metadata", {})
    )

    print("Stored in vector DB ✅")
