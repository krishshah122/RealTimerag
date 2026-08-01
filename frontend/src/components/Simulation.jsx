import { useState, useEffect } from "react";
import { supabase } from "../supabaseClient";
import { generateAlerts } from "../api";

export default function Simulation() {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [team, setTeam] = useState("Loading...");
    const [bulkCount, setBulkCount] = useState(10);

    useEffect(() => {
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
            icon: "🐛",
            color: "#3b82f6",
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
            icon: "🔴",
            color: "#ef4444",
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
            icon: "🚀",
            color: "#f59e0b",
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
            icon: "🛡️",
            color: "#10b981",
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

    async function triggerBulkGeneration() {
        setLoading(true);
        try {
            const result = await generateAlerts(bulkCount);
            setLogs(prev => [{
                time: new Date().toLocaleTimeString(),
                message: `Generated ${result.generated} simulated alerts`,
                details: `Ingested via Alert Generator for team ${team}`,
            }, ...prev]);
        } catch (err) {
            setLogs(prev => [{
                time: new Date().toLocaleTimeString(),
                message: `Error: ${err.message}`,
                isError: true,
            }, ...prev]);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="ask-page" style={{ alignItems: 'stretch', maxWidth: 960, margin: '0 auto' }}>
            {/* Hero */}
            <div className="ask-hero" style={{ textAlign: 'left', maxWidth: '100%' }}>
                <span className="ask-hero-icon" style={{ fontSize: 40 }}>🛠️</span>
                <h1 style={{ fontSize: 36 }}>Incident Simulation</h1>
                <p>
                    Simulate automated events from external tools. These incidents will be
                    ingested by the RAG system and tagged with your current team.
                </p>
            </div>

            {/* Team Context Banner */}
            <div className="glass-card" style={{ 
                display: 'flex', alignItems: 'center', gap: 12, 
                marginBottom: 28, padding: '16px 24px',
                background: 'rgba(99,102,241,0.08)', 
                borderColor: 'rgba(99,102,241,0.2)' 
            }}>
                <span style={{ fontSize: 20 }}>👤</span>
                <span style={{ color: 'var(--text-secondary)', fontSize: 14 }}>
                    <strong style={{ color: 'var(--text-accent)' }}>Current Context:</strong> Simulating events for Team{' '}
                    <strong style={{ color: 'var(--text-primary)', textTransform: 'uppercase' }}>{team}</strong>
                </span>
            </div>

            {/* Alert Generator */}
            <div className="glass-card" style={{ marginBottom: 28, padding: '20px 24px' }}>
                <div className="section-title blue" style={{ fontSize: 18 }}>
                    <span className="icon">⚡</span>
                    Automated Alert Generator
                </div>
                <p style={{ color: 'var(--text-secondary)', marginBottom: 16, fontSize: 14 }}>
                    Generate realistic monitoring alerts (CPU spikes, connection exhaustion, latency, etc.)
                    and stream them through Kafka into the vector index.
                </p>
                <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                    <input
                        type="number"
                        min={1}
                        max={100}
                        value={bulkCount}
                        onChange={(e) => setBulkCount(Number(e.target.value))}
                        style={{ width: 80, padding: 10, borderRadius: 8, border: '1px solid var(--border-color)' }}
                    />
                    <button
                        onClick={triggerBulkGeneration}
                        disabled={loading}
                        style={{
                            padding: '12px 24px',
                            background: 'var(--gradient-primary)',
                            color: 'white', border: 'none', borderRadius: 8,
                            fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
                        }}
                    >
                        {loading ? 'Generating...' : `Generate ${bulkCount} Alerts`}
                    </button>
                </div>
            </div>

            {/* Scenario Buttons */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 36 }}>
                {scenarios.map(scenario => (
                    <button
                        key={scenario.id}
                        onClick={() => triggerScenario(scenario)}
                        disabled={loading}
                        style={{
                            padding: '20px 16px',
                            background: `linear-gradient(135deg, ${scenario.color}22, ${scenario.color}11)`,
                            border: `1px solid ${scenario.color}44`,
                            color: 'var(--text-primary)',
                            borderRadius: 'var(--radius-md)',
                            fontWeight: 600,
                            fontSize: 14,
                            cursor: loading ? 'not-allowed' : 'pointer',
                            opacity: loading ? 0.5 : 1,
                            transition: 'all 0.2s',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            gap: 10,
                            fontFamily: 'inherit',
                        }}
                        onMouseOver={(e) => {
                            if (!loading) {
                                e.currentTarget.style.transform = 'translateY(-3px)';
                                e.currentTarget.style.boxShadow = `0 8px 24px ${scenario.color}33`;
                            }
                        }}
                        onMouseOut={(e) => {
                            if (!loading) {
                                e.currentTarget.style.transform = 'translateY(0)';
                                e.currentTarget.style.boxShadow = 'none';
                            }
                        }}
                    >
                        <span style={{ fontSize: 28 }}>{scenario.icon}</span>
                        <span>{scenario.label}</span>
                    </button>
                ))}
            </div>

            {/* Manual Entry Section */}
            <div className="glass-card" style={{ marginBottom: 36 }}>
                <div className="section-title blue" style={{ fontSize: 18 }}>
                    <span className="icon">✍️</span>
                    Log Custom Issue
                </div>
                <p style={{ color: 'var(--text-secondary)', marginBottom: 20, fontSize: 14 }}>
                    Type a human-readable description. The system will automatically format it as a structured JSON incident for your team.
                </p>
                <form onSubmit={(e) => {
                    e.preventDefault();
                    const formData = new FormData(e.target);
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
                    <div style={{ display: 'grid', gap: 16, marginBottom: 16 }}>
                        <div>
                            <label style={{ display: 'block', marginBottom: 6, fontWeight: 600, color: 'var(--text-secondary)', fontSize: 13 }}>Issue Description</label>
                            <textarea
                                name="text"
                                required
                                placeholder="e.g., 'The payment API is returning 500 errors intermittently.'"
                                style={{
                                    width: '100%', padding: 14, borderRadius: 'var(--radius-sm)',
                                    border: '1px solid var(--border-color)', minHeight: 80,
                                    background: 'var(--bg-input)', color: 'var(--text-primary)',
                                    fontFamily: 'inherit', fontSize: 14, resize: 'vertical', outline: 'none'
                                }}
                            />
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                            <div>
                                <label style={{ display: 'block', marginBottom: 6, fontWeight: 600, color: 'var(--text-secondary)', fontSize: 13 }}>Type</label>
                                <select name="type" style={{
                                    width: '100%', padding: 12, borderRadius: 'var(--radius-sm)',
                                    border: '1px solid var(--border-color)', background: 'var(--bg-input)',
                                    color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 14, outline: 'none'
                                }}>
                                    <option value="incident">Incident</option>
                                    <option value="bug">Bug Report</option>
                                    <option value="deployment">Deployment</option>
                                    <option value="alert">Alert</option>
                                </select>
                            </div>
                            <div>
                                <label style={{ display: 'block', marginBottom: 6, fontWeight: 600, color: 'var(--text-secondary)', fontSize: 13 }}>Severity</label>
                                <select name="severity" style={{
                                    width: '100%', padding: 12, borderRadius: 'var(--radius-sm)',
                                    border: '1px solid var(--border-color)', background: 'var(--bg-input)',
                                    color: 'var(--text-primary)', fontFamily: 'inherit', fontSize: 14, outline: 'none'
                                }}>
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
                            width: '100%', padding: 14,
                            background: 'var(--gradient-primary)',
                            color: 'white', border: 'none',
                            borderRadius: 'var(--radius-sm)',
                            fontWeight: 700, fontSize: 15,
                            cursor: loading ? 'not-allowed' : 'pointer',
                            opacity: loading ? 0.5 : 1,
                            fontFamily: 'inherit',
                            boxShadow: '0 4px 14px rgba(99,102,241,0.35)',
                            transition: 'all 0.15s'
                        }}
                    >
                        {loading ? 'Logging Issue...' : 'Log Issue →'}
                    </button>
                </form>
            </div>

            {/* Live Event Log */}
            <div className="glass-card">
                <div className="section-title green" style={{ fontSize: 18 }}>
                    <span className="icon">📡</span>
                    Live Event Log
                </div>
                {logs.length === 0 ? (
                    <div className="empty-state">No events triggered yet.</div>
                ) : (
                    <div>
                        {logs.map((log, idx) => (
                            <div key={idx} className="list-item" style={{ fontFamily: "'Inter', monospace", fontSize: 13 }}>
                                <span style={{ color: 'var(--text-muted)', marginRight: 10 }}>[{log.time}]</span>
                                <strong style={{ color: log.isError ? '#f87171' : '#34d399' }}>{log.message}</strong>
                                {!log.isError && <span style={{ marginLeft: 10, color: 'var(--text-secondary)' }}>({log.details})</span>}
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
