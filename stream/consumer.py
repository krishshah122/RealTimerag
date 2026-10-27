from kafka import KafkaConsumer
from collections import deque
from datetime import datetime, timezone
import json
import time

from core.vector_store import VectorStore
from stream.kafka_config import (
    get_consumer_group_id,
    get_issue_topic,
    get_kafka_config,
)

store = VectorStore()
issue_topic = get_issue_topic()

consumer = KafkaConsumer(
    issue_topic,
    **get_kafka_config(),
    group_id=get_consumer_group_id(),
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    auto_offset_reset="earliest",
    enable_auto_commit=False,
)

consumer_group_id = get_consumer_group_id()
print(f"Kafka consumer started (group={consumer_group_id}, topic={issue_topic})...")

processed_at = deque()
consumer_started_at = time.perf_counter()


def _event_age_ms(timestamp):
    if not timestamp:
        return None
    try:
        event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - event_time).total_seconds() * 1000)
    except (TypeError, ValueError):
        return None


for message in consumer:
    started = time.perf_counter()
    event = message.value

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
    consumer.commit()
    completed_at = time.perf_counter()
    processed_at.append(completed_at)
    while processed_at and completed_at - processed_at[0] > 60:
        processed_at.popleft()
    elapsed_ms = (completed_at - started) * 1000
    age_ms = _event_age_ms(
        event.get("ingest_started_at") or event.get("timestamp")
    )
    elapsed_window = min(60.0, completed_at - consumer_started_at)
    throughput = len(processed_at) / max(elapsed_window, 1.0)
    print(
        "Indexed incident "
        f"id={event.get('id', 'unknown')} group={consumer_group_id} "
        f"topic={message.topic} partition={message.partition} offset={message.offset} "
        f"backend={store.backend_name} upsert_and_commit_ms={elapsed_ms:.1f} "
        f"event_age_ms={age_ms if age_ms is not None else 'unknown'} "
        f"events_per_second_60s={throughput:.2f}"
    )
