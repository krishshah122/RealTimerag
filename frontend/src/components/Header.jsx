import { useEffect, useState } from "react";
import { supabase } from "../supabaseClient";
import { useNavigate } from "react-router-dom";

export default function Header() {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Fetch session and profile
    async function getUserData() {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user) {
        setUser(session.user);

        // Fetch profile for team name
        const { data } = await supabase
          .from("profiles")
          .select("team_name")
          .eq("id", session.user.id)
          .single();

        if (data) setProfile(data);
      }
    }
    getUserData();

    // Listen for auth changes to update header dynamically
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      if (!session) setProfile(null);
    });

    return () => subscription.unsubscribe();
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    navigate("/login");
  }

  return (
    <header className="header">
      <div className="header-title">
        ⚡ Real-Time RAG
      </div>

      {user && (
        <div className="header-user">
          <button
            onClick={() => navigate("/simulation")}
            style={{
              background: 'none',
              border: '1px solid #e5e7eb',
              padding: '6px 12px',
              borderRadius: '6px',
              cursor: 'pointer',
              marginRight: '10px',
              color: '#4b5563',
              fontSize: '14px'
            }}
          >
            🛠️ Simulate
          </button>
          <span>
            {user.email}
            {profile?.team_name && <strong style={{ color: '#4f46e5' }}> ({profile.team_name})</strong>}
          </span>
          <button onClick={handleLogout} className="btn-logout">
            Logout
          </button>
        </div>
      )}
    </header>
  );
}
