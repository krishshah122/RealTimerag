import React, { useState } from 'react';
import { QueryAnalyticsChart } from './QueryAnalyticsChart';
import { IssuesDashboard } from './IssuesDashboard';
import { TrendingIssuesCard } from './TrendingIssuesCard';

export function AnalyticsPage() {
  const [hours, setHours] = useState(24);
  const [refreshKey, setRefreshKey] = useState(0);

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
              <p>Real-time query analytics, issue tracking, and team performance metrics</p>
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
