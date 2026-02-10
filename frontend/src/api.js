import { supabase } from "./supabaseClient";

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