"""
Incident lifecycle management — persistent incident records with status,
severity, summarization fields, correlation groups, and timeline events.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from core.analytics import engine as analytics_engine

Base = declarative_base()
Session = sessionmaker(bind=analytics_engine)


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    MITIGATED = "MITIGATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


VALID_TRANSITIONS = {
    IncidentStatus.OPEN: {IncidentStatus.INVESTIGATING, IncidentStatus.MITIGATED, IncidentStatus.RESOLVED},
    IncidentStatus.INVESTIGATING: {IncidentStatus.MITIGATED, IncidentStatus.RESOLVED, IncidentStatus.OPEN},
    IncidentStatus.MITIGATED: {IncidentStatus.RESOLVED, IncidentStatus.INVESTIGATING},
    IncidentStatus.RESOLVED: {IncidentStatus.CLOSED, IncidentStatus.INVESTIGATING},
    IncidentStatus.CLOSED: {IncidentStatus.OPEN},
}


class Incident(Base):
    __tablename__ = "incidents"

    incident_id = Column(String(100), primary_key=True)
    status = Column(String(30), default=IncidentStatus.OPEN.value)
    severity = Column(String(20), default="medium")
    service = Column(String(100), nullable=True)
    team = Column(String(50))
    issue_type = Column(String(50), default="alert")
    text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    created_by_user_id = Column(String(100), nullable=True)
    created_by_email = Column(String(255), nullable=True)
    summary = Column(Text, nullable=True)
    root_cause = Column(Text, nullable=True)
    impact = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    correlation_group = Column(String(100), nullable=True)
    archived = Column(Boolean, default=False)


class IncidentTimelineEvent(Base):
    __tablename__ = "incident_timeline"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(String(100), index=True)
    event_type = Column(String(50))
    description = Column(Text)
    user_id = Column(String(100), nullable=True)
    user_email = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


class WebNotification(Base):
    __tablename__ = "web_notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), index=True)
    incident_id = Column(String(100), nullable=True)
    channel = Column(String(30), default="web")
    title = Column(String(200))
    message = Column(Text)
    read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(analytics_engine)


def _incident_to_dict(i: Incident) -> dict:
    return {
        "incident_id": i.incident_id,
        "status": i.status,
        "severity": i.severity,
        "service": i.service,
        "team": i.team,
        "issue_type": i.issue_type,
        "text": i.text,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "resolved_at": i.resolved_at.isoformat() if i.resolved_at else None,
        "created_by_user_id": i.created_by_user_id,
        "created_by_email": i.created_by_email,
        "summary": i.summary,
        "root_cause": i.root_cause,
        "impact": i.impact,
        "recommendation": i.recommendation,
        "correlation_group": i.correlation_group,
        "archived": i.archived,
    }


class IncidentManager:
    @staticmethod
    def create(
        incident_id: str,
        text: str,
        team: str,
        issue_type: str = "alert",
        severity: str = "medium",
        service: str | None = None,
        created_by_user_id: str | None = None,
        created_by_email: str | None = None,
        correlation_group: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        session = Session()
        try:
            inc = Incident()
            inc.incident_id = incident_id
            inc.text = text
            inc.team = team
            inc.issue_type = issue_type
            inc.severity = (severity or "medium").lower()
            inc.service = service or (metadata or {}).get("service")
            inc.created_by_user_id = created_by_user_id
            inc.created_by_email = created_by_email
            inc.correlation_group = correlation_group
            inc.status = IncidentStatus.OPEN.value
            inc.created_at = datetime.utcnow()
            session.add(inc)
            session.commit()

            IncidentManager.add_timeline_event(
                incident_id,
                "created",
                f"Incident created: {text[:120]}",
                created_by_user_id,
                created_by_email,
            )
            return _incident_to_dict(inc)
        finally:
            session.close()

    @staticmethod
    def add_timeline_event(
        incident_id: str,
        event_type: str,
        description: str,
        user_id: str | None = None,
        user_email: str | None = None,
    ):
        session = Session()
        try:
            ev = IncidentTimelineEvent()
            ev.incident_id = incident_id
            ev.event_type = event_type
            ev.description = description
            ev.user_id = user_id
            ev.user_email = user_email
            ev.timestamp = datetime.utcnow()
            session.add(ev)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def get(incident_id: str) -> Optional[dict]:
        session = Session()
        try:
            inc = session.query(Incident).filter(Incident.incident_id == incident_id).first()
            return _incident_to_dict(inc) if inc else None
        finally:
            session.close()

    @staticmethod
    def list_incidents(
        team: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        hours: int | None = None,
        include_archived: bool = False,
        limit: int = 100,
    ) -> list[dict]:
        session = Session()
        try:
            q = session.query(Incident)
            if not include_archived:
                q = q.filter(Incident.archived == False)  # noqa: E712
            if team:
                q = q.filter(Incident.team == team)
            if status:
                q = q.filter(Incident.status == status.upper())
            if severity:
                q = q.filter(Incident.severity == severity.lower())
            if hours:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                q = q.filter(Incident.created_at >= cutoff)
            incidents = q.order_by(Incident.created_at.desc()).limit(limit).all()
            return [_incident_to_dict(i) for i in incidents]
        finally:
            session.close()

    @staticmethod
    def transition_status(
        incident_id: str,
        new_status: str,
        user_id: str | None = None,
        user_email: str | None = None,
    ) -> dict:
        session = Session()
        try:
            inc = session.query(Incident).filter(Incident.incident_id == incident_id).first()
            if not inc:
                raise ValueError("Incident not found")

            current = IncidentStatus(inc.status)
            target = IncidentStatus(new_status.upper())
            if target not in VALID_TRANSITIONS.get(current, set()):
                raise ValueError(f"Cannot transition from {current.value} to {target.value}")

            inc.status = target.value
            if target in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
                inc.resolved_at = datetime.utcnow()
            elif target == IncidentStatus.OPEN:
                inc.resolved_at = None

            session.commit()
            IncidentManager.add_timeline_event(
                incident_id,
                f"status_{target.value.lower()}",
                f"Status changed to {target.value}",
                user_id,
                user_email,
            )
            return _incident_to_dict(inc)
        finally:
            session.close()

    @staticmethod
    def update_summary(
        incident_id: str,
        summary: str | None = None,
        root_cause: str | None = None,
        impact: str | None = None,
        recommendation: str | None = None,
    ) -> dict:
        session = Session()
        try:
            inc = session.query(Incident).filter(Incident.incident_id == incident_id).first()
            if not inc:
                raise ValueError("Incident not found")
            if summary is not None:
                inc.summary = summary
            if root_cause is not None:
                inc.root_cause = root_cause
            if impact is not None:
                inc.impact = impact
            if recommendation is not None:
                inc.recommendation = recommendation
            session.commit()
            return _incident_to_dict(inc)
        finally:
            session.close()

    @staticmethod
    def set_correlation_group(incident_id: str, group_id: str) -> dict:
        session = Session()
        try:
            inc = session.query(Incident).filter(Incident.incident_id == incident_id).first()
            if not inc:
                raise ValueError("Incident not found")
            inc.correlation_group = group_id
            session.commit()
            return _incident_to_dict(inc)
        finally:
            session.close()

    @staticmethod
    def get_timeline(incident_id: str) -> list[dict]:
        session = Session()
        try:
            events = (
                session.query(IncidentTimelineEvent)
                .filter(IncidentTimelineEvent.incident_id == incident_id)
                .order_by(IncidentTimelineEvent.timestamp.asc())
                .all()
            )
            return [
                {
                    "id": e.id,
                    "event_type": e.event_type,
                    "description": e.description,
                    "user_id": e.user_id,
                    "user_email": e.user_email,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in events
            ]
        finally:
            session.close()

    @staticmethod
    def get_correlation_group(group_id: str) -> list[dict]:
        session = Session()
        try:
            incidents = (
                session.query(Incident)
                .filter(Incident.correlation_group == group_id)
                .order_by(Incident.created_at.asc())
                .all()
            )
            return [_incident_to_dict(i) for i in incidents]
        finally:
            session.close()

    @staticmethod
    def archive_resolved_older_than(days: int) -> int:
        session = Session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            count = (
                session.query(Incident)
                .filter(
                    Incident.status.in_([IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value]),
                    Incident.resolved_at != None,  # noqa: E711
                    Incident.resolved_at < cutoff,
                    Incident.archived == False,  # noqa: E712
                )
                .update({"archived": True})
            )
            session.commit()
            return count
        finally:
            session.close()

    @staticmethod
    def get_expired_incident_ids(days: int) -> list[str]:
        session = Session()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            rows = (
                session.query(Incident.incident_id)
                .filter(
                    Incident.archived == True,  # noqa: E712
                    Incident.resolved_at != None,  # noqa: E711
                    Incident.resolved_at < cutoff,
                )
                .all()
            )
            return [r[0] for r in rows]
        finally:
            session.close()

    @staticmethod
    def delete_incident(incident_id: str) -> bool:
        session = Session()
        try:
            session.query(IncidentTimelineEvent).filter(
                IncidentTimelineEvent.incident_id == incident_id
            ).delete()
            deleted = (
                session.query(Incident).filter(Incident.incident_id == incident_id).delete()
            )
            session.commit()
            return deleted > 0
        finally:
            session.close()

    @staticmethod
    def get_mttr_stats(hours: int = 168) -> dict:
        session = Session()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            resolved = (
                session.query(Incident)
                .filter(
                    Incident.resolved_at != None,  # noqa: E711
                    Incident.created_at >= cutoff,
                )
                .all()
            )
            if not resolved:
                return {"mttr_minutes": 0, "resolved_count": 0}
            durations = [
                (i.resolved_at - i.created_at).total_seconds() / 60
                for i in resolved
                if i.resolved_at and i.created_at
            ]
            return {
                "mttr_minutes": round(sum(durations) / len(durations), 1),
                "resolved_count": len(durations),
            }
        finally:
            session.close()

    @staticmethod
    def get_severity_distribution(hours: int = 168) -> dict:
        session = Session()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            incidents = session.query(Incident).filter(Incident.created_at >= cutoff).all()
            dist: dict[str, int] = {}
            for i in incidents:
                dist[i.severity or "unknown"] = dist.get(i.severity or "unknown", 0) + 1
            return dist
        finally:
            session.close()

    @staticmethod
    def get_top_services(hours: int = 168, limit: int = 10) -> list[dict]:
        session = Session()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            incidents = session.query(Incident).filter(Incident.created_at >= cutoff).all()
            counts: dict[str, int] = {}
            for i in incidents:
                svc = i.service or "unknown"
                counts[svc] = counts.get(svc, 0) + 1
            ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
            return [{"service": s, "count": c} for s, c in ranked]
        finally:
            session.close()
