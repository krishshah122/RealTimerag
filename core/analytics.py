"""
Analytics & Insights Module

Tracks:
- Query analytics (questions, response times, accuracy)
- Issue ingestion metrics (by team, type, over time)
- Trending issues (frequency, patterns)
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy import Column, String, Float, DateTime, Integer, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import json
from collections import Counter, defaultdict

# SQLite for analytics (lightweight, no external DB needed)
engine = create_engine("sqlite:///rag_analytics.db")
Base = declarative_base()
Session = sessionmaker(bind=engine)


class QueryAnalytic(Base):
    """Track query metrics"""
    __tablename__ = "query_analytics"
    
    query_id = Column(String(50), primary_key=True)
    question = Column(String(500))
    team = Column(String(50))
    response_time = Column(Float)  # ms
    accuracy = Column(Float)  # 0.0-1.0
    timestamp = Column(DateTime, default=datetime.utcnow)


class IssueAnalytic(Base):
    """Track issue metrics"""
    __tablename__ = "issue_analytics"
    
    issue_id = Column(String(100), primary_key=True)
    issue_type = Column(String(50))
    team = Column(String(50))
    text = Column(String(200))
    created_by_user_id = Column(String(100), nullable=True)
    created_by_email = Column(String(255), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


# Create tables
Base.metadata.create_all(engine)


def _ensure_issue_analytics_columns():
    """Lightweight SQLite migration for issue ownership fields."""
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(issue_analytics)")).fetchall()
        column_names = {row[1] for row in rows}
        if "created_by_user_id" not in column_names:
            conn.execute(text("ALTER TABLE issue_analytics ADD COLUMN created_by_user_id VARCHAR(100)"))
        if "created_by_email" not in column_names:
            conn.execute(text("ALTER TABLE issue_analytics ADD COLUMN created_by_email VARCHAR(255)"))


_ensure_issue_analytics_columns()


class AnalyticsManager:
    """Lightweight analytics tracking and querying"""
    
    @staticmethod
    def track_query(query_id: str, question: str, team: Optional[str], response_time: float, accuracy: float = 0.85):
        """Log a query"""
        session = Session()
        try:
            q = QueryAnalytic()
            q.query_id = query_id
            q.question = question[:500]
            q.team = team or "unknown"
            q.response_time = response_time
            q.accuracy = accuracy
            q.timestamp = datetime.utcnow()
            session.add(q)
            session.commit()
        finally:
            session.close()
    
    @staticmethod
    def track_issue(
        issue_id: str,
        issue_type: str,
        team: Optional[str],
        text: str,
        created_by_user_id: Optional[str] = None,
        created_by_email: Optional[str] = None,
    ):
        """Log an issue"""
        session = Session()
        try:
            i = IssueAnalytic()
            i.issue_id = issue_id
            i.issue_type = issue_type
            i.team = team or "unknown"
            i.text = text[:200]
            i.created_by_user_id = created_by_user_id
            i.created_by_email = created_by_email
            i.timestamp = datetime.utcnow()
            session.add(i)
            session.commit()
        finally:
            session.close()

    @staticmethod
    def get_issue(issue_id: str) -> Optional[dict]:
        """Fetch a single issue record by id."""
        session = Session()
        try:
            issue = session.query(IssueAnalytic).filter(IssueAnalytic.issue_id == issue_id).first()
            if issue is None:
                return None
            return {
                "issue_id": issue.issue_id,
                "issue_type": issue.issue_type,
                "team": issue.team,
                "text": issue.text,
                "created_by_user_id": issue.created_by_user_id,
                "created_by_email": issue.created_by_email,
                "timestamp": issue.timestamp.isoformat() if issue.timestamp else None,
            }
        finally:
            session.close()

    @staticmethod
    def list_user_issues(user_id: str, hours: Optional[int] = None) -> list[dict]:
        """List issues created by a specific user."""
        session = Session()
        try:
            query = session.query(IssueAnalytic).filter(IssueAnalytic.created_by_user_id == user_id)
            if hours is not None:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                query = query.filter(IssueAnalytic.timestamp >= cutoff)

            issues = query.order_by(IssueAnalytic.timestamp.desc()).all()
            return [
                {
                    "issue_id": issue.issue_id,
                    "issue_type": issue.issue_type,
                    "team": issue.team,
                    "text": issue.text,
                    "created_by_user_id": issue.created_by_user_id,
                    "created_by_email": issue.created_by_email,
                    "timestamp": issue.timestamp.isoformat() if issue.timestamp else None,
                }
                for issue in issues
            ]
        finally:
            session.close()

    @staticmethod
    def delete_issue(issue_id: str) -> bool:
        """Delete a single issue analytics record by id."""
        session = Session()
        try:
            issue = session.query(IssueAnalytic).filter(IssueAnalytic.issue_id == issue_id).first()
            if issue is None:
                return False
            session.delete(issue)
            session.commit()
            return True
        finally:
            session.close()
    
    @staticmethod
    def get_query_stats(hours: int = 24) -> dict:
        """Get query analytics for last N hours"""
        session = Session()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            queries = session.query(QueryAnalytic).filter(QueryAnalytic.timestamp >= cutoff).all()
            
            if not queries:
                return {"total_queries": 0, "by_team": {}, "avg_response_time": 0, "avg_accuracy": 0, "top_questions": []}
            
            teams_data = defaultdict(lambda: {"count": 0, "avg_response_time": 0, "avg_accuracy": 0, "times": [], "accuracies": []})
            top_questions = Counter([q.question for q in queries])
            
            for q in queries:
                teams_data[q.team]["count"] += 1
                teams_data[q.team]["times"].append(q.response_time)
                teams_data[q.team]["accuracies"].append(q.accuracy)
            
            # Calculate averages
            for team, data in teams_data.items():
                data["avg_response_time"] = round(sum(data["times"]) / len(data["times"]), 2)
                data["avg_accuracy"] = round(sum(data["accuracies"]) / len(data["accuracies"]), 2)
                del data["times"]
                del data["accuracies"]
            
            return {
                "total_queries": len(queries),
                "by_team": dict(teams_data),
                "avg_response_time": round(sum(q.response_time for q in queries) / len(queries), 2),
                "avg_accuracy": round(sum(q.accuracy for q in queries) / len(queries), 2),
                "top_questions": [{"question": q, "count": c} for q, c in top_questions.most_common(5)]
            }
        finally:
            session.close()
    
    @staticmethod
    def get_issue_stats(hours: int = 24) -> dict:
        """Get issue analytics for last N hours"""
        session = Session()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            issues = session.query(IssueAnalytic).filter(IssueAnalytic.timestamp >= cutoff).all()
            
            if not issues:
                return {"total_issues": 0, "by_team": {}, "by_type": {}, "trending": []}
            
            by_team = defaultdict(int)
            by_type = defaultdict(int)
            trending = Counter([i.issue_type for i in issues])
            
            for issue in issues:
                by_team[issue.team] += 1
                by_type[issue.issue_type] += 1
            
            return {
                "total_issues": len(issues),
                "by_team": dict(by_team),
                "by_type": dict(by_type),
                "trending": [{"type": t, "count": c, "percentage": round(c/len(issues)*100, 1)} for t, c in trending.most_common(5)]
            }
        finally:
            session.close()
    
    @staticmethod
    def get_time_series(hours: int = 24, interval_minutes: int = 60) -> dict:
        """Get issue count over time"""
        session = Session()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            issues = session.query(IssueAnalytic).filter(IssueAnalytic.timestamp >= cutoff).all()
            
            timeline = defaultdict(int)
            for issue in issues:
                bucket = issue.timestamp.replace(minute=0, second=0, microsecond=0)
                timeline[bucket.isoformat()] += 1
            
            sorted_timeline = sorted(timeline.items())
            return {"timeline": [{"timestamp": ts, "count": count} for ts, count in sorted_timeline]}
        finally:
            session.close()
