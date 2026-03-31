import React, { useEffect, useState } from 'react';
import { getIssues, getMyIssues, deleteIssue } from './api';

export function IssuesDashboard({ hours = 24, onIssueDeleted }) {
  const [summary, setSummary] = useState(null);
  const [myIssues, setMyIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState(null);

  async function loadData() {
    setLoading(true);
    try {
      const [issues, mine] = await Promise.all([getIssues(hours), getMyIssues()]);
      setSummary(issues);
      setMyIssues(mine.issues || []);
    } catch (e) {
      console.error('Failed to fetch issues:', e);
      setSummary(null);
      setMyIssues([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [hours]);

  async function handleDelete(issueId) {
    if (!window.confirm('Delete this issue from your analytics and indexed data?')) {
      return;
    }

    setDeletingId(issueId);
    try {
      await deleteIssue(issueId);
      await loadData();
      onIssueDeleted?.();
    } catch (e) {
      console.error('Failed to delete issue:', e);
      alert(e.message || 'Failed to delete issue');
    } finally {
      setDeletingId(null);
    }
  }

  if (loading) {
    return (
      <div className="glass-card">
        <div className="loading-state">
          <div className="loading-spinner" />
          Loading issues...
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="glass-card">
        <div className="error-state">Failed to load issue data</div>
      </div>
    );
  }

  const byTeam = summary.by_team || {};
  const byType = summary.by_type || {};

  return (
    <div className="glass-card">
      <div className="section-title orange">
        <span className="icon">Issues</span>
        Issues Dashboard
      </div>

      <div className="issues-total-banner">
        <div className="label">Total Issues Ingested</div>
        <div className="value">{summary.total_issues || 0}</div>
        <div className="sub">Issues flowing through pipeline</div>
      </div>

      <div style={{ marginBottom: 24 }}>
        <div className="section-title blue" style={{ fontSize: 16 }}>
          <span className="icon">Mine</span>
          My Logged Issues
        </div>
        {myIssues.length === 0 ? (
          <div className="empty-state">No issues created by your account yet</div>
        ) : (
          myIssues.map((issue) => (
            <div key={issue.issue_id} className="list-item" style={{ marginBottom: 12 }}>
              <div className="list-item-row" style={{ alignItems: 'flex-start', gap: 12 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                    {issue.issue_type || 'unknown'}
                  </div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: 13, marginBottom: 6 }}>
                    {issue.text}
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
                    ID: {issue.issue_id} | Team: {issue.team || 'unknown'}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(issue.issue_id)}
                  disabled={deletingId === issue.issue_id}
                  className="badge orange"
                  style={{ border: 'none', cursor: deletingId === issue.issue_id ? 'not-allowed' : 'pointer' }}
                >
                  {deletingId === issue.issue_id ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div style={{ marginBottom: 24 }}>
        <div className="section-title orange" style={{ fontSize: 16 }}>
          <span className="icon">Teams</span>
          By Team
        </div>
        {Object.entries(byTeam).length === 0 ? (
          <div className="empty-state">No data yet</div>
        ) : (
          Object.entries(byTeam).map(([team, count], i) => {
            const pct = summary.total_issues > 0 ? ((count / summary.total_issues) * 100).toFixed(1) : 0;
            return (
              <div key={i} style={{ marginBottom: 14 }}>
                <div className="list-item-row">
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14 }}>{team}</span>
                  <span className="badge orange">{count}</span>
                </div>
                <div className="progress-track">
                  <div className="progress-fill orange" style={{ width: `${pct}%` }} />
                </div>
                <div className="progress-label">{pct}% of total</div>
              </div>
            );
          })
        )}
      </div>

      <div>
        <div className="section-title green" style={{ fontSize: 16 }}>
          <span className="icon">Types</span>
          By Type
        </div>
        {Object.entries(byType).length === 0 ? (
          <div className="empty-state">No data yet</div>
        ) : (
          Object.entries(byType).map(([type, count], i) => {
            const pct = summary.total_issues > 0 ? ((count / summary.total_issues) * 100).toFixed(1) : 0;
            return (
              <div key={i} style={{ marginBottom: 14 }}>
                <div className="list-item-row">
                  <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14, textTransform: 'capitalize' }}>{type}</span>
                  <span className="badge green">{count}</span>
                </div>
                <div className="progress-track">
                  <div className="progress-fill green" style={{ width: `${pct}%` }} />
                </div>
                <div className="progress-label">{pct}% of total</div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
