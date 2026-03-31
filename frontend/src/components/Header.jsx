import { useEffect, useState } from "react";
import { supabase } from "../supabaseClient";
import { useNavigate, useLocation } from "react-router-dom";

export default function Header() {
  const [user, setUser] = useState(null);
  const [profile, setProfile] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    async function getUserData() {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.user) {
        setUser(session.user);

        const { data } = await supabase
          .from("profiles")
          .select("team_name")
          .eq("id", session.user.id)
          .single();

        if (data) setProfile(data);
      }
    }
    getUserData();

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

  const isActive = (path) => location.pathname === path;

  return (
    <header className="header">
      <div
        className="header-title"
        style={{ cursor: 'pointer' }}
        onClick={() => navigate("/ask")}
      >
        ⚡ Real-Time RAG
      </div>

      {user && (
        <div className="header-user">
          <button
            className="nav-btn"
            onClick={() => navigate("/ask")}
            style={isActive("/ask") ? { background: 'rgba(99,102,241,0.15)', borderColor: 'rgba(99,102,241,0.4)', color: '#818cf8' } : {}}
          >
            🧠 Ask AI
          </button>
          <button
            className="nav-btn"
            onClick={() => navigate("/simulation")}
            style={isActive("/simulation") ? { background: 'rgba(99,102,241,0.15)', borderColor: 'rgba(99,102,241,0.4)', color: '#818cf8' } : {}}
          >
            🛠️ Simulate
          </button>
          <button
            className="nav-btn"
            onClick={() => navigate("/analytics")}
            style={isActive("/analytics") ? { background: 'rgba(99,102,241,0.15)', borderColor: 'rgba(99,102,241,0.4)', color: '#818cf8' } : {}}
          >
            📊 Analytics
          </button>
          <span>
            {user.email}
            {profile?.team_name && (
              <strong style={{ color: '#818cf8', marginLeft: 4 }}>
                ({profile.team_name})
              </strong>
            )}
          </span>
          <button onClick={handleLogout} className="btn-logout">
            Logout
          </button>
        </div>
      )}
    </header>
  );
}
