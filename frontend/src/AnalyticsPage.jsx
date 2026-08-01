import React, { useState, useEffect } from 'react';
import { QueryAnalyticsChart } from './QueryAnalyticsChart';
import { IssuesDashboard } from './IssuesDashboard';
import { TrendingIssuesCard } from './TrendingIssuesCard';
import { getDashboard } from './api';

function MetricCard({ label, value, unit, color }) {
  return (
    <div className="glass-card" style={{ textAlign: 'center', padding: 20 }}>
      <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 32, fontWeight: 700, color: color || 'var(--text-accent)' }}>
        {value}{unit && <span style={{ fontSize: 16 }}>{unit}</span>}
      </div>
    </div>
  );
}

export function AnalyticsPage() {
  const [hours, setHours] = useState(24);
  const [refreshKey, setRefreshKey] = useState(0);
  const [dashboard, setDashboard] = useState(null);

  useEffect(() => {
    getDashboard(hours).then(setDashboard).catch(console.error);
  }, [hours, refreshKey]);

  const timeOptions = [
    { label: '1 Hour', value: 1 },
    { label: '6 Hours', value: 6 },
    { label: '24 Hours', value: 24 },
    { label: '1 Week', value: 168 },
  ];

  return (
    <div className="analytics-page">
      <div className="analytics-hero">
        <div className="analytics-hero-inner">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
            <div>
              <div className="analytics-hero-badge">
                <span className="pulse-dot" />
                Live Dashboard
              </div>
              <h1>Analytics & Insights</h1>
              <p>MTTR, incident frequency, severity distribution, and team performance</p>
            </div>
          </div>

          <div className="time-filters">
            {timeOptions.map(({ label, value }) => (
              <button
                key={value}
                onClick={() => setHours(value)}
                className={`time-pill${hours === value ? ' active' : ''}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {dashboard && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, padding: '0 24px 24px' }}>
          <MetricCard label="Total Queries" value={dashboard.queries?.total_queries || 0} />
          <MetricCard label="Total Incidents" value={dashboard.issues?.total_issues || 0} color="#f59e0b" />
          <MetricCard label="MTTR" value={dashboard.mttr?.mttr_minutes || 0} unit=" min" color="#10b981" />
          <MetricCard label="Resolved" value={dashboard.mttr?.resolved_count || 0} color="#3b82f6" />
          <MetricCard label="Avg Response" value={dashboard.queries?.avg_response_time || 0} unit=" ms" />
        </div>
      )}

      {dashboard?.severity_distribution && (
        <div className="glass-card" style={{ margin: '0 24px 24px', padding: 20 }}>
          <h3 style={{ marginBottom: 12 }}>Severity Distribution</h3>
          <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
            {Object.entries(dashboard.severity_distribution).map(([sev, count]) => (
              <div key={sev} style={{ padding: '8px 16px', borderRadius: 8, background: 'rgba(99,102,241,0.1)' }}>
                <strong style={{ textTransform: 'uppercase' }}>{sev}</strong>: {count}
              </div>
            ))}
          </div>
        </div>
      )}

      {dashboard?.top_services?.length > 0 && (
        <div className="glass-card" style={{ margin: '0 24px 24px', padding: 20 }}>
          <h3 style={{ marginBottom: 12 }}>Top Affected Services</h3>
          {dashboard.top_services.map((s) => (
            <div key={s.service} className="list-item" style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span>{s.service}</span>
              <strong>{s.count}</strong>
            </div>
          ))}
        </div>
      )}

      <div className="analytics-content" key={refreshKey}>
        <QueryAnalyticsChart hours={hours} />
        <div className="analytics-grid-split">
          <IssuesDashboard hours={hours} onIssueDeleted={() => setRefreshKey((k) => k + 1)} />
          <TrendingIssuesCard hours={hours} />
        </div>
      </div>

      <div className="analytics-footer">
        <span className="pulse-dot" />
        Last updated: {new Date().toLocaleTimeString()} - real-time data
      </div>
    </div>
  );
}
