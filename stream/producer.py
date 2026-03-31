import json

producer = None

def _get_producer():
    global producer
    if producer is None:
        try:
            from kafka import KafkaProducer
            producer = KafkaProducer(
                bootstrap_servers="localhost:9092",
                value_serializer=lambda v: json.dumps(v).encode("utf-8")
            )
        except Exception as e:
            print(f"Kafka producer init failed: {e}")
            return None
    return producer

def send_issue_event(event: dict):
    p = _get_producer()
    if p is None:
        print("Kafka not available, skipping event send")
        return
    p.send("live_issues", event)
    p.flush()
