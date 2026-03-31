import { supabase } from "./supabaseClient";

const API_BASE = "http://127.0.0.1:8000";

async function getAuthHeader() {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
}

export async function askQuestion(question, teamId) {
  // Ensure we have a valid session
  const { data: { session } } = await supabase.auth.getSession();
  const accessToken = session?.access_token;

  if (!accessToken) {
    console.warn("No active session found in askQuestion");
  }

  const url = new URL("http://127.0.0.1:8000/ask");
  if (teamId) {
    url.searchParams.set("team_id", teamId);
  }

  const response = await fetch(url.toString(), {
    method: "POST",
    headers: {
      "Content-Type": "text/plain", // Tell the server this is raw text
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: question // Just send the string directly!
  });

  if (!response.ok) {
    throw new Error("Server error");
  }

  return response.json();
}

// Analytics API functions
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
  const res = await fetch(`${API_BASE}/issues/${issueId}`, {
    method: "DELETE",
    headers,
  });
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

