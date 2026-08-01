import { supabase } from "./supabaseClient";

const API_BASE = "http://127.0.0.1:8000";

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
}

export async function askQuestion(question, teamId, filters = {}) {
  const { data: { session } } = await supabase.auth.getSession();
  const accessToken = session?.access_token;

  const url = new URL(`${API_BASE}/ask`);
  if (teamId) url.searchParams.set("team_id", teamId);
  if (filters.status) url.searchParams.set("status", filters.status);
  if (filters.severity) url.searchParams.set("severity", filters.severity);

  const response = await fetch(url.toString(), {
    method: "POST",
    headers: {
      "Content-Type": "text/plain",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: question,
  });

  if (!response.ok) throw new Error("Server error");
  return response.json();
}

export async function summarizeIncidents(query, teamId) {
  const headers = await getAuthHeader();
  const url = new URL(`${API_BASE}/summarize`);
  if (teamId) url.searchParams.set("team_id", teamId);
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "text/plain", ...headers },
    body: query,
  });
  if (!res.ok) throw new Error("Summarize failed");
  return res.json();
}

export async function getRecommendation(query, teamId) {
  const headers = await getAuthHeader();
  const url = new URL(`${API_BASE}/recommend`);
  if (teamId) url.searchParams.set("team_id", teamId);
  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "text/plain", ...headers },
    body: query,
  });
  if (!res.ok) throw new Error("Recommendation failed");
  return res.json();
}

export async function getIncidents(params = {}) {
  const headers = await getAuthHeader();
  const url = new URL(`${API_BASE}/incidents`);
  Object.entries(params).forEach(([k, v]) => { if (v) url.searchParams.set(k, v); });
  const res = await fetch(url.toString(), { headers });
  if (!res.ok) throw new Error("Failed to fetch incidents");
  return res.json();
}

export async function getIncident(incidentId) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`, { headers });
  if (!res.ok) throw new Error("Failed to fetch incident");
  return res.json();
}

export async function updateIncidentStatus(incidentId, status) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new Error("Status update failed");
  return res.json();
}

export async function getSimilarIncidents(incidentId) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/similar`, { headers });
  if (!res.ok) throw new Error("Failed to fetch similar incidents");
  return res.json();
}

export async function getIncidentRCA(incidentId) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/rca`, { headers });
  if (!res.ok) throw new Error("RCA generation failed");
  return res.json();
}

export async function getNotifications(unreadOnly = false) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/notifications?unread_only=${unreadOnly}`, { headers });
  if (!res.ok) throw new Error("Failed to fetch notifications");
  return res.json();
}

export async function markNotificationRead(id) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/notifications/${id}/read`, { method: "POST", headers });
  if (!res.ok) throw new Error("Failed to mark read");
  return res.json();
}

export async function generateAlerts(count = 10) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/simulation/generate?count=${count}`, {
    method: "POST",
    headers,
  });
  if (!res.ok) throw new Error("Alert generation failed");
  return res.json();
}

export async function getQueries(hours = 24) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/analytics/queries?hours=${hours}`, { headers });
  if (!res.ok) throw new Error("Failed to fetch queries");
  return res.json();
}

export async function getIssues(hours = 24) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/analytics/issues?hours=${hours}`, { headers });
  if (!res.ok) throw new Error("Failed to fetch issues");
  return res.json();
}

export async function getMyIssues() {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/issues/mine`, { headers });
  if (!res.ok) throw new Error("Failed to fetch your issues");
  return res.json();
}

export async function deleteIssue(issueId) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/issues/${issueId}`, { method: "DELETE", headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Failed to delete issue");
  }
  return res.json();
}

export async function getTimeline(hours = 24) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/analytics/timeline?hours=${hours}`, { headers });
  if (!res.ok) throw new Error("Failed to fetch timeline");
  return res.json();
}

export async function getDashboard(hours = 24) {
  const headers = await getAuthHeader();
  const res = await fetch(`${API_BASE}/analytics/dashboard?hours=${hours}`, { headers });
  if (!res.ok) throw new Error("Failed to fetch dashboard");
  return res.json();
}
