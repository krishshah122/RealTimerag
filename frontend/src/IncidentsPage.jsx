import { useState, useEffect } from "react";
import {
  getIncidents,
  getIncident,
  updateIncidentStatus,
  getSimilarIncidents,
  getIncidentRCA,
} from "./api";

const STATUSES = ["OPEN", "INVESTIGATING", "MITIGATED", "RESOLVED", "CLOSED"];
const STATUS_COLORS = {
  OPEN: "#ef4444",
  INVESTIGATING: "#f59e0b",
  MITIGATED: "#3b82f6",
  RESOLVED: "#10b981",
  CLOSED: "#6b7280",
};

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [rca, setRca] = useState(null);
  const [similar, setSimilar] = useState([]);

  useEffect(() => {
    loadIncidents();
  }, [statusFilter, severityFilter]);

  async function loadIncidents() {
    setLoading(true);
    try {
      const params = { hours: 168 };
      if (statusFilter) params.status = statusFilter;
      if (severityFilter) params.severity = severityFilter;
      const data = await getIncidents(params);
      setIncidents(data.incidents || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function selectIncident(id) {
    setSelected(id);
    setRca(null);
    setSimilar([]);
    try {
      const data = await getIncident(id);
      setDetail(data);
      const sim = await getSimilarIncidents(id);
      setSimilar(sim.similar || []);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleStatusChange(newStatus) {
    if (!selected) return;
    try {
      await updateIncidentStatus(selected, newStatus);
      await selectIncident(selected);
      await loadIncidents();
    } catch (e) {
      alert(e.message);
    }
  }

  async function handleGenerateRCA() {
    if (!selected) return;
    try {
      const data = await getIncidentRCA(selected);
      setRca(data.rca);
    } catch (e) {
      alert(e.message);
    }
  }

  return (
    <div className="analytics-page">
      <div className="analytics-hero">
        <div className="analytics-hero-inner">
          <h1>Incident Lifecycle</h1>
          <p>Manage incident status, view timelines, correlation groups, and similar incidents</p>
          <div className="time-filters" style={{ marginTop: 16 }}>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: 8, marginRight: 8 }}
            >
              <option value="">All Statuses</option>
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              style={{ padding: "8px 12px", borderRadius: 8 }}
            >
              <option value="">All Severities</option>
              {["critical", "high", "medium", "low"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 24, padding: "0 24px 48px" }}>
        <div className="glass-card">
          <h3 style={{ marginBottom: 16 }}>Incidents ({incidents.length})</h3>
          {loading ? (
            <p>Loading...</p>
          ) : incidents.length === 0 ? (
            <p className="empty-state">No incidents found</p>
          ) : (
            incidents.map((inc) => (
              <div
                key={inc.incident_id}
                onClick={() => selectIncident(inc.incident_id)}
                className="list-item"
                style={{
                  cursor: "pointer",
                  borderLeft: `3px solid ${STATUS_COLORS[inc.status] || "#666"}`,
                  background: selected === inc.incident_id ? "rgba(99,102,241,0.1)" : undefined,
                }}
              >
                <strong>{inc.incident_id}</strong>
                <span style={{ marginLeft: 8, color: STATUS_COLORS[inc.status] }}>{inc.status}</span>
                <span style={{ marginLeft: 8, fontSize: 12, color: "#888" }}>{inc.severity}</span>
                <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--text-secondary)" }}>
                  {inc.text?.slice(0, 80)}...
                </p>
              </div>
            ))
          )}
        </div>

        <div className="glass-card">
          {!detail ? (
            <p className="empty-state">Select an incident to view details</p>
          ) : (
            <>
              <h3>{detail.incident.incident_id} — {detail.incident.service || "Unknown Service"}</h3>
              <p style={{ color: "var(--text-secondary)" }}>{detail.incident.text}</p>

              {detail.incident.summary && (
                <div style={{ marginTop: 16 }}>
                  <strong>Summary:</strong> {detail.incident.summary}
                </div>
              )}
              {detail.incident.recommendation && (
                <div style={{ marginTop: 8, padding: 12, background: "rgba(16,185,129,0.1)", borderRadius: 8 }}>
                  <strong>Recommendation:</strong> {detail.incident.recommendation}
                </div>
              )}

              <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {STATUSES.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleStatusChange(s)}
                    disabled={detail.incident.status === s}
                    style={{
                      padding: "6px 12px",
                      borderRadius: 6,
                      border: `1px solid ${STATUS_COLORS[s]}`,
                      background: detail.incident.status === s ? STATUS_COLORS[s] : "transparent",
                      color: detail.incident.status === s ? "#fff" : STATUS_COLORS[s],
                      cursor: "pointer",
                      fontSize: 12,
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>

              <button onClick={handleGenerateRCA} style={{ marginTop: 16, padding: "10px 20px", cursor: "pointer" }}>
                Generate RCA Report
              </button>

              {rca && (
                <div style={{ marginTop: 16, padding: 16, background: "var(--bg-input)", borderRadius: 8, whiteSpace: "pre-wrap", fontSize: 14 }}>
                  {rca}
                </div>
              )}

              <h4 style={{ marginTop: 24 }}>Timeline</h4>
              {(detail.timeline || []).map((ev) => (
                <div key={ev.id} className="list-item" style={{ fontSize: 13 }}>
                  <span style={{ color: "#888" }}>[{ev.timestamp?.slice(11, 19)}]</span>{" "}
                  <strong>{ev.event_type}</strong>: {ev.description}
                </div>
              ))}

              {detail.correlated?.length > 1 && (
                <>
                  <h4 style={{ marginTop: 24 }}>Correlated Incidents ({detail.correlated.length})</h4>
                  {detail.correlated.map((c) => (
                    <div key={c.incident_id} className="list-item" style={{ fontSize: 13 }}>
                      {c.incident_id}: {c.text?.slice(0, 60)}...
                    </div>
                  ))}
                </>
              )}

              {similar.length > 0 && (
                <>
                  <h4 style={{ marginTop: 24 }}>Similar Historical Incidents</h4>
                  {similar.map((s) => (
                    <div key={s.issue_id} className="list-item" style={{ fontSize: 13 }}>
                      <strong>{s.issue_id}</strong> (score: {s.score?.toFixed(2)}) — {s.text?.slice(0, 60)}...
                    </div>
                  ))}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
