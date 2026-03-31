import React, { useEffect, useState } from 'react';
import { getQueries } from './api';

export function QueryAnalyticsChart({ hours = 24 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const queries = await getQueries(hours);
        setData(queries);
      } catch (e) {
        console.error('Failed to fetch queries:', e);
      } finally {
        setLoading(false);
      }
    })();
  }, [hours]);

  if (loading) {
    return (
      <div className="glass-card" style={{ marginBottom: 32 }}>
        <div className="loading-state">
          <div className="loading-spinner" />
          Loading query analytics…
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass-card" style={{ marginBottom: 32 }}>
        <div className="error-state">Failed to load query data</div>
      </div>
    );
  }

  const topQuestions = data.top_questions || [];
  const byTeam = data.by_team || {};

  return (
    <div style={{ marginBottom: 32 }}>
      {/* Stat Cards Row */}
      <div className="stat-cards-row">
        <div className="stat-card blue">
          <div className="stat-card-label">📊 Total Queries</div>
          <div className="stat-card-value">{data.total_queries || 0}</div>
          <div className="stat-card-footer">Asked in selected period</div>
        </div>

        <div className="stat-card green">
          <div className="stat-card-label">⚡ Avg Response Time</div>
          <div className="stat-card-value">
            {(data.avg_response_time || 0).toFixed(0)}
            <span>ms</span>
          </div>
          <div className="stat-card-footer">Quick & responsive</div>
        </div>

        <div className="stat-card purple">
          <div className="stat-card-label">✅ Avg Accuracy</div>
          <div className="stat-card-value">
            {((data.avg_accuracy || 0) * 100).toFixed(0)}
            <span>%</span>
          </div>
          <div className="stat-card-footer">Answer quality</div>
        </div>
      </div>

      {/* Two-Column: Top Questions + By Team */}
      <div className="analytics-grid-2">
        {/* Top Questions */}
        <div className="glass-card">
          <div className="section-title blue">
            <span className="icon">🔥</span>
            Top Questions
          </div>
          {topQuestions.length === 0 ? (
            <div className="empty-state">No questions yet</div>
          ) : (
            topQuestions.slice(0, 5).map((q, i) => (
              <div key={i} className="list-item">
                <div className="list-item-title">{q.question}</div>
                <div className="list-item-meta">
                  🔔 Asked {q.count} {q.count === 1 ? 'time' : 'times'}
                </div>
              </div>
            ))
          )}
        </div>

        {/* By Team */}
        <div className="glass-card">
          <div className="section-title green">
            <span className="icon">👥</span>
            By Team
          </div>
          {Object.entries(byTeam).length === 0 ? (
            <div className="empty-state">No team data yet</div>
          ) : (
            Object.entries(byTeam).map(([team, stats], i) => (
              <div key={i} className="list-item">
                <div className="list-item-row">
                  <div className="list-item-title" style={{ marginBottom: 0 }}>{team}</div>
                  <span className="badge green">{stats.count}</span>
                </div>
                <div className="list-item-meta" style={{ marginTop: 8 }}>
                  ⏱️ {stats.avg_response_time.toFixed(0)}ms &nbsp;•&nbsp; ✅ {(stats.avg_accuracy * 100).toFixed(0)}%
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
