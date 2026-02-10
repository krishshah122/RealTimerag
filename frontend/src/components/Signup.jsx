import { useState } from "react";
import { supabase } from "../supabaseClient";
import { useNavigate, Link } from "react-router-dom";

export default function Signup() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [team, setTeam] = useState("ops"); // Default to 'ops'
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const navigate = useNavigate();

    async function handleSignup(e) {
        e.preventDefault();
        setLoading(true);
        setError("");
        setSuccess("");

        try {
            // Call our backend /register endpoint
            const response = await fetch("http://localhost:8000/register", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    email,
                    password,
                    team,
                }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Registration failed");
            }

            setSuccess("Account created successfully! Logging you in...");

            // Automatically log the user in after successful registration
            const { error: loginError } = await supabase.auth.signInWithPassword({
                email,
                password,
            });

            if (loginError) {
                setError("Account created, but auto-login failed. Please log in manually.");
                setTimeout(() => navigate("/login"), 2000);
            } else {
                setTimeout(() => navigate("/ask"), 1000);
            }

        } catch (err) {
            console.error("Signup error:", err);
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="login-container">
            <div className="login-card">
                <div className="login-header">
                    <h2>Create Account</h2>
                    <p>Join Real-Time RAG</p>
                </div>

                {error && <div className="error-message">{error}</div>}
                {success && <div className="success-message">{success}</div>}

                <form onSubmit={handleSignup}>
                    <div className="form-group">
                        <label htmlFor="email">Email Address</label>
                        <input
                            id="email"
                            type="email"
                            className="input-field"
                            placeholder="you@example.com"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="password">Password</label>
                        <input
                            id="password"
                            type="password"
                            className="input-field"
                            placeholder="••••••••"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            minLength={6}
                        />
                    </div>

                    <div className="form-group">
                        <label htmlFor="team">Team</label>
                        <select
                            id="team"
                            className="input-field"
                            value={team}
                            onChange={(e) => setTeam(e.target.value)}
                        >
                            <option value="ops">Operations (Ops)</option>
                            <option value="devops">DevOps</option>
                            <option value="security">Security</option>
                        </select>
                        <p style={{ fontSize: "12px", color: "#6b7280", marginTop: "4px" }}>
                            Determines what data you can access.
                        </p>
                    </div>

                    <button type="submit" className="btn-primary" disabled={loading}>
                        {loading ? "Creating Account..." : "Sign Up"}
                    </button>
                </form>

                <button
                    className="btn-secondary"
                    onClick={() => navigate("/login")}
                >
                    Already have an account? Log in
                </button>
            </div>
        </div>
    );
}
