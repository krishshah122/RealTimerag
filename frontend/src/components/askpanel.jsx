import { useState } from "react";
import { askQuestion } from "../api";

export default function AskPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleAsk() {
    if (!question.trim()) return;

    setLoading(true);
    setError("");
    setAnswer("");

    try {
      const data = await askQuestion(question);

      // Handle all backend response shapes
      if (typeof data === "string") {
        setAnswer(data);
      } else if (data.answer) {
        setAnswer(data.answer);
      } else if (data.output) {
        setAnswer(data.output);
      } else {
        setAnswer(JSON.stringify(data, null, 2));
      }
    } catch (err) {
      console.error(err);
      setError("Failed to fetch answer from server");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  }

  const suggestions = [
    "What are the top issues this week?",
    "Any critical alerts right now?",
    "Show me delay trends",
    "Summarize recent incidents",
  ];

  return (
    <div className="ask-page">
      {/* Hero Section */}
      <div className="ask-hero">
        <span className="ask-hero-icon">🧠</span>
        <h1>Ask Your AI Assistant</h1>
        <p>
          Get real-time answers about live issues, alerts, delays, and
          operational insights — powered by RAG intelligence.
        </p>
      </div>

      {/* Ask Panel */}
      <div className="ask-panel">
        <textarea
          placeholder="Ask about live issues, delays, alerts..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
        />

        <button onClick={handleAsk} disabled={loading}>
          {loading ? (
            <>
              <span className="loading-spinner" style={{ display: 'inline-block', width: 16, height: 16, borderWidth: 2, marginRight: 8, verticalAlign: 'middle' }} />
              Thinking…
            </>
          ) : (
            "Ask AI →"
          )}
        </button>

        {error && <div className="error">{error}</div>}

        {answer && (
          <div className="answer-box">
            <strong>🤖 AI Response</strong>
            <p>{answer}</p>
          </div>
        )}
      </div>

      {/* Suggestion Chips */}
      {!answer && (
        <div className="ask-suggestions">
          {suggestions.map((s, i) => (
            <button
              key={i}
              className="suggestion-chip"
              onClick={() => {
                setQuestion(s);
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
