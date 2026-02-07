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

  return (
    <div className="ask-panel">
      <textarea
        placeholder="Ask about live issues, delays, alerts..."
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
      />

      <button onClick={handleAsk} disabled={loading}>
        {loading ? "Thinking..." : "Ask"}
      </button>

      {error && <div className="error">{error}</div>}

      {answer && (
        <div className="answer-box">
          <strong>Answer</strong>
          <p>{answer}</p>
        </div>
      )}
    </div>
  );
}
