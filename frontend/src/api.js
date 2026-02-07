export async function askQuestion(question) {
  const response = await fetch("http://127.0.0.1:8000/ask", {
    method: "POST",
    headers: {
      "Content-Type": "text/plain" // Tell the server this is raw text
    },
    body: question // Just send the string directly!
  });

  if (!response.ok) {
    throw new Error("Server error");
  }

  return response.json(); 
}