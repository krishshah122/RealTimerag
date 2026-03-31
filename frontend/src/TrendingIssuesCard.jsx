import React, { useEffect, useState } from 'react';
import { getTimeline } from './api';

export function TrendingIssuesCard({ hours = 24 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const timeline = await getTimeline(hours);
        setData(timeline);
      } catch (e) {
        console.error('Failed to fetch trending:', e);
      } finally {
        setLoading(false);
      }
    })();
  }, [hours]);

  if (loading) {
    return (
      <div className="glass-card">
        <div className="loading-state">
          <div className="loading-spinner" />
          Loading trends…
        </div>
      </div>
    );
  }

  if (!data || !data.timeline) {
    return (
      <div className="glass-card">
        <div className="error-state">Failed to load trending data</div>
      </div>
    );
  }

  const timeline = data.timeline || [];
  const hourData = timeline.map((h, i) => ({
    hour: i,
    count: h.count,
    time: new Date(h.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  }));

  const maxCount = Math.max(...hourData.map((h) => h.count), 1);
  const recentTop = hourData.slice(-5).reverse();

  return (
    <div className="glass-card">
      <div className="section-title pink">
        <span className="icon">🔥</span>
        Trending Right Now
      </div>

      {recentTop.length === 0 ? (
        <div className="empty-state">No recent activity</div>
      ) : (
        recentTop.map((item, i) => (
          <div key={i} className="trending-bar-item">
            <div className="trending-bar-header">
              <div className="trending-bar-time">{item.time}</div>
              <div className="trending-bar-label">Peak Activity</div>
            </div>

            <div className="trending-bar-track">
              <div
                className="trending-bar-fill"
                style={{ width: `${Math.max((item.count / maxCount) * 100, 15)}%` }}
              >
                <span>{item.count}</span>
              </div>
            </div>

            <div className="trending-bar-sub">
              {item.count} issue{item.count !== 1 ? 's' : ''} ingested this hour
            </div>
          </div>
        ))
      )}

      {/* Summary */}
      <div className="trending-summary">
        <span className="icon">📊</span>
        <div>
          <div className="info-label">Current Peak</div>
          <div className="info-value">
            {recentTop.length > 0 ? recentTop[0].count : 0} issues
          </div>
        </div>
      </div>
    </div>
  );
}
