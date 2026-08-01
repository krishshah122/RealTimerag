import random
import uuid
from datetime import datetime

TEAMS = ["backend", "devops", "security", "ops", "platform", "data"]
SERVICES = [
    "payment-service", "api-gateway", "user-service", "notification-service",
    "order-service", "inventory-db", "search-index", "auth-service",
]
SEVERITIES = ["low", "medium", "high", "critical"]
ALERT_TEMPLATES = [
    ("CPU > 90%", "critical", "CPU utilization exceeded 90% on {service} for 5+ minutes"),
    ("Memory leak detected", "high", "Memory usage growing unbounded on {service} — possible leak"),
    ("API latency spike", "high", "P99 latency on {service} exceeded 2s threshold"),
    ("Database connection exhaustion", "critical", "Connection pool exhausted on {service} — active queries blocking"),
    ("Disk usage exceeded threshold", "high", "Disk usage at 92% on {service} node"),
    ("5xx error rate spike", "critical", "Error rate on {service} exceeded 5% over last 10 minutes"),
    ("Queue backlog growing", "medium", "Message queue depth on {service} exceeded 10,000 messages"),
    ("SSL certificate expiring", "medium", "TLS certificate for {service} expires in 7 days"),
    ("Pod crash loop", "high", "Kubernetes pod for {service} in CrashLoopBackOff state"),
    ("Cache miss rate spike", "medium", "Redis cache miss rate on {service} exceeded 40%"),
]


def generate_alert(team: str | None = None) -> dict:
    template = random.choice(ALERT_TEMPLATES)
    service = random.choice(SERVICES)
    team = team or random.choice(TEAMS)
    severity = template[1]
    text = template[2].format(service=service)

    status_roll = random.random()
    if status_roll < 0.3:
        status = "OPEN"
    elif status_roll < 0.5:
        status = "INVESTIGATING"
    elif status_roll < 0.7:
        status = "MITIGATED"
    elif status_roll < 0.9:
        status = "RESOLVED"
    else:
        status = "CLOSED"

    return {
        "type": "alert",
        "text": text,
        "metadata": {
            "severity": severity,
            "service": service,
            "source": "AlertGenerator",
            "alert_type": template[0],
            "status": status,
            "simulated": True,
        },
    }


def generate_batch(count: int = 10, team: str | None = None) -> list[dict]:
    return [generate_alert(team) for _ in range(count)]
