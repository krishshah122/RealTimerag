"""Multi-channel notification delivery."""

import json
import smtplib
from email.mime.text import MIMEText
from typing import Optional

import httpx

from config import (
    NOTIFY_FROM_EMAIL,
    SLACK_WEBHOOK_URL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    TEAMS_WEBHOOK_URL,
)
from core.incidents import IncidentManager, WebNotification, Session


def _store_web_notification(
    user_id: str,
    title: str,
    message: str,
    incident_id: str | None = None,
):
    session = Session()
    try:
        n = WebNotification()
        n.user_id = user_id
        n.incident_id = incident_id
        n.channel = "web"
        n.title = title
        n.message = message
        session.add(n)
        session.commit()
    finally:
        session.close()


def send_slack(message: str, title: str = "Incident Alert") -> bool:
    if not SLACK_WEBHOOK_URL:
        print(f"[SLACK stub] {title}: {message[:200]}")
        return False
    try:
        payload = {"text": f"*{title}*\n{message}"}
        httpx.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Slack notification failed: {e}")
        return False


def send_teams(message: str, title: str = "Incident Alert") -> bool:
    if not TEAMS_WEBHOOK_URL:
        print(f"[TEAMS stub] {title}: {message[:200]}")
        return False
    try:
        payload = {"@type": "MessageCard", "summary": title, "text": f"**{title}**\n\n{message}"}
        httpx.post(TEAMS_WEBHOOK_URL, json=payload, timeout=10)
        return True
    except Exception as e:
        print(f"Teams notification failed: {e}")
        return False


def send_email(to_email: str, subject: str, body: str) -> bool:
    if not SMTP_HOST or not to_email:
        print(f"[EMAIL stub] To: {to_email} | {subject}: {body[:200]}")
        return False
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = NOTIFY_FROM_EMAIL
        msg["To"] = to_email
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Email notification failed: {e}")
        return False


def notify_incident_created(
    incident: dict,
    user_id: str | None = None,
    user_email: str | None = None,
    channels: list[str] | None = None,
):
    """Dispatch notifications when a new incident is ingested."""
    channels = channels or ["web", "slack"]
    severity = incident.get("severity", "medium")
    title = f"[{severity.upper()}] {incident.get('service', 'Incident')}"
    message = incident.get("text", "")
    recommendation = incident.get("recommendation")
    if recommendation:
        message += f"\n\nRecommended Action:\n{recommendation}"

    if "web" in channels and user_id:
        _store_web_notification(user_id, title, message, incident.get("incident_id"))

    if "slack" in channels:
        send_slack(message, title)

    if "teams" in channels:
        send_teams(message, title)

    if "email" in channels and user_email:
        send_email(user_email, title, message)


def list_web_notifications(user_id: str, unread_only: bool = False) -> list[dict]:
    session = Session()
    try:
        q = session.query(WebNotification).filter(WebNotification.user_id == user_id)
        if unread_only:
            q = q.filter(WebNotification.read == False)  # noqa: E712
        rows = q.order_by(WebNotification.created_at.desc()).limit(50).all()
        return [
            {
                "id": n.id,
                "incident_id": n.incident_id,
                "channel": n.channel,
                "title": n.title,
                "message": n.message,
                "read": n.read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ]
    finally:
        session.close()


def mark_notification_read(notification_id: int, user_id: str) -> bool:
    session = Session()
    try:
        n = (
            session.query(WebNotification)
            .filter(WebNotification.id == notification_id, WebNotification.user_id == user_id)
            .first()
        )
        if not n:
            return False
        n.read = True
        session.commit()
        return True
    finally:
        session.close()
