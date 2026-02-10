import { useState } from "react";
import { askQuestion } from "../api";

const TEAMS = [
  { id: "operations", label: "Operations" },
  { id: "devops", label: "DevOps" },
  { id: "security", label: "Security" },
  { id: "support", label: "Support" },
  { id: "analytics", label: "Analytics" },
];

export default function TeamDashboard() {
  const [activeTeam, setActiveTeam] = useState(TEAMS[0].id);
  const [messages, setMessages] = useState([]); // Store chat history
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  // Clear history when switching teams (optional, but cleaner)
  const handleTeamChange = (teamId) => {
    setActiveTeam(teamId);
    setMessages([]);
  };

  async function handleAsk() {
    if (!question.trim()) return;

    // Add user message immediately
    const userMsg = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setQuestion("");
    setLoading(true);

    try {
      const data = await askQuestion(userMsg.content, activeTeam);

      let botContent = "No answer returned.";
      if (typeof data === "string") botContent = data;
      else if (data.answer) botContent = data.answer;
      else if (data.output) botContent = data.output;
      else botContent = JSON.stringify(data, null, 2);

      const botMsg = { role: "assistant", content: botContent };
      setMessages((prev) => [...prev, botMsg]);

    } catch (err) {
      console.error(err);
      const errorMsg = { role: "system", content: "Failed to fetch answer." };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="team-dashboard">
      <div className="tabs">
        {TEAMS.map((team) => (
          <button
            key={team.id}
            className={team.id === activeTeam ? "tab active" : "tab"}
            onClick={() => handleTeamChange(team.id)}
          >
            {team.label}
          </button>
        ))}
      </div>

      <div className="tab-content chat-container">
        <h2>{TEAMS.find((t) => t.id === activeTeam)?.label} Chatbot</h2>

        <div className="chat-history">
          {messages.length === 0 && (
            <div className="empty-state">
              Ask a question to start the conversation...
            </div>
          )}
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-content">{msg.content}</div>
            </div>
          ))}
          {loading && <div className="message assistant"><div className="message-content">Thinking...</div></div>}
        </div>

        <div className="chat-input-area">
          <textarea
            placeholder={`Ask the ${activeTeam} chatbot...`}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleAsk();
              }
            }}
          />
          <button onClick={handleAsk} disabled={loading}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

