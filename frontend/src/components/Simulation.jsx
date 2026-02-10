import { useState } from "react";
import { supabase } from "../supabaseClient";

export default function Simulation() {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [team, setTeam] = useState("Loading...");

    // Fetch team on mount
    useState(() => {
        supabase.auth.getSession().then(({ data: { session } }) => {
            if (session?.user) {
                supabase
                    .from("profiles")
                    .select("team_name")
                    .eq("id", session.user.id)
                    .single()
                    .then(({ data }) => {
                        setTeam(data?.team_name || "Unknown");
                    });
            }
        });
    }, []);

    const scenarios = [
        {
            id: "jira-bug",
            label: "Jira: Critical Bug",
            color: "#3b82f6", // Blue
            data: {
                text: "Checkout page returns 500 error when user clicks 'Pay Now'. Payment gateway timeout.",
                type: "bug",
                metadata: {
                    priority: "Blocker",
                    source: "Jira",
                    ticket_id: "PROD-2391"
                }
            }
        },
        {
            id: "pd-alert",
            label: "PagerDuty: DB High CPU",
            color: "#ef4444", // Red
            data: {
                text: "CRITICAL: Database primary node (db-01) CPU usage > 95% for 5 minutes.",
                type: "alert",
                metadata: {
                    severity: "Critical",
                    source: "PagerDuty",
                    region: "us-east-1"
                }
            }
        },
        {
            id: "jenkins-deploy",
            label: "Jenkins: Deploy Failed",
            color: "#f59e0b", // Amber
            data: {
                text: "Deployment #8841 to production failed. Health check timed out after 300s.",
                type: "deployment",
                metadata: {
                    service: "api-gateway",
                    source: "Jenkins",
                    build_url: "jenkins/job/deploy/8841"
                }
            }
        },
        {
            id: "splunk-log",
            label: "Splunk: Security Warning",
            color: "#10b981", // Emerald
            data: {
                text: "Multiple failed login attempts detected from IP 192.168.1.55 (Brute Force Pattern).",
                type: "security_event",
                metadata: {
                    level: "Warning",
                    source: "Splunk",
                    user_agent: "Unknown"
                }
            }
        }
    ];

    async function triggerScenario(scenario) {
        setLoading(true);
        try {
            const { data: { session } } = await supabase.auth.getSession();
            if (!session) {
                throw new Error("You must be logged in to trigger simulations.");
            }

            const response = await fetch("http://localhost:8000/log_issue", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${session.access_token}`
                },
                body: JSON.stringify(scenario.data)
            });

            const result = await response.json();

            if (!response.ok) throw new Error("Failed to log issue");

            // Add to local log
            const logEntry = {
                time: new Date().toLocaleTimeString(),
                message: `Triggered ${scenario.label}`,
                details: `Tagged as Team: ${result.event.team_tag}`
            };

            setLogs(prev => [logEntry, ...prev]);

        } catch (err) {
            console.error(err);
            setLogs(prev => [{
                time: new Date().toLocaleTimeString(),
                message: `Error: ${err.message}`,
                isError: true
            }, ...prev]);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="container" style={{ maxWidth: '800px', margin: '0 auto', padding: '20px' }}>
            <h2 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px', color: '#1f2937' }}>
                🛠️ Incident Simulation
            </h2>
            <p style={{ color: '#4b5563', marginBottom: '30px' }}>
                Simulate automated events from external tools. These incidents will be
                ingested by the RAG system and tagged with your current team.
            </p>

            <div style={{ backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', padding: '12px', borderRadius: '8px', marginBottom: '20px', color: '#1e40af' }}>
                <strong>Current Context:</strong> You are simulating events for Team <span style={{ textTransform: 'uppercase', fontWeight: 'bold' }}>{team}</span>.
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '40px' }}>
                {scenarios.map(scenario => (
                    <button
                        key={scenario.id}
                        onClick={() => triggerScenario(scenario)}
                        disabled={loading}
                        style={{
                            padding: '16px',
                            backgroundColor: scenario.color,
                            color: 'white',
                            border: 'none',
                            borderRadius: '8px',
                            fontWeight: '600',
                            cursor: loading ? 'not-allowed' : 'pointer',
                            opacity: loading ? 0.7 : 1,
                            transition: 'transform 0.1s',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: '8px'
                        }}
                        onMouseOver={(e) => !loading && (e.currentTarget.style.transform = 'scale(1.02)')}
                        onMouseOut={(e) => !loading && (e.currentTarget.style.transform = 'scale(1)')}
                    >
                        <span>{scenario.label}</span>
                    </button>
                ))}
            </div>

            {/* Manual Entry Section */}
            <div style={{ background: 'white', padding: '24px', borderRadius: '12px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', marginBottom: '40px' }}>
                <h3 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '16px', color: '#1f2937' }}>
                    ✍️ Log Custom Issue
                </h3>
                <p style={{ color: '#6b7280', marginBottom: '20px' }}>
                    Type a human-readable description. The system will automatically format it as a structured JSON incident for your team.
                </p>
                <form onSubmit={(e) => {
                    e.preventDefault();
                    const formData = new FormData(e.target);
                    // Construct the JSON payload
                    const customScenario = {
                        label: "Custom Issue",
                        data: {
                            text: formData.get("text"),
                            type: formData.get("type"),
                            metadata: {
                                source: "Manual Entry",
                                severity: formData.get("severity")
                            }
                        }
                    };
                    triggerScenario(customScenario);
                    e.target.reset();
                }}>
                    <div style={{ display: 'grid', gap: '16px', marginBottom: '16px' }}>
                        <div>
                            <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>Issue Description</label>
                            <textarea
                                name="text"
                                required
                                placeholder="e.g., 'The payment API is returning 500 errors intermittently.'"
                                style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db', minHeight: '80px' }}
                            />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>Type</label>
                                <select name="type" style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db' }}>
                                    <option value="incident">Incident</option>
                                    <option value="bug">Bug Report</option>
                                    <option value="deployment">Deployment</option>
                                    <option value="alert">Alert</option>
                                </select>
                            </div>
                            <div>
                                <label style={{ display: 'block', marginBottom: '8px', fontWeight: '500', color: '#374151' }}>Severity</label>
                                <select name="severity" style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db' }}>
                                    <option value="low">Low</option>
                                    <option value="medium">Medium</option>
                                    <option value="high">High</option>
                                    <option value="critical">Critical</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    <button
                        type="submit"
                        disabled={loading}
                        style={{
                            width: '100%',
                            padding: '12px',
                            backgroundColor: '#4f46e5',
                            color: 'white',
                            border: 'none',
                            borderRadius: '8px',
                            fontWeight: '600',
                            cursor: loading ? 'not-allowed' : 'pointer',
                            opacity: loading ? 0.7 : 1
                        }}
                    >
                        {loading ? 'Logging Issue...' : 'Log Issue'}
                    </button>
                </form>
            </div>

            <div className="simulation-logs" style={{ background: '#f3f4f6', padding: '20px', borderRadius: '12px' }}>
                <h3 style={{ fontSize: '18px', fontWeight: 'bold', marginBottom: '12px', color: '#374151' }}>
                    Live Event Log
                </h3>
                {logs.length === 0 ? (
                    <p style={{ color: '#9ca3af', fontStyle: 'italic' }}>No events triggered yet.</p>
                ) : (
                    <ul style={{ listStyle: 'none', padding: 0 }}>
                        {logs.map((log, idx) => (
                            <li key={idx} style={{
                                padding: '8px 0',
                                borderBottom: '1px solid #e5e7eb',
                                color: log.isError ? '#dc2626' : '#059669',
                                fontFamily: 'monospace'
                            }}>
                                <span style={{ color: '#6b7280', marginRight: '10px' }}>[{log.time}]</span>
                                <strong>{log.message}</strong>
                                {!log.isError && <span style={{ marginLeft: '10px', color: '#4b5563' }}>({log.details})</span>}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
