
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";
const STORAGE_KEY = "hikari-chat-v1";

const ideas = [
  { icon: "✧", title: "Write code", desc: "Build something useful" },
  { icon: "▤", title: "Summarize", desc: "Make sense of anything" },
  { icon: "◇", title: "Create images", desc: "Explore creative ideas" },
  { icon: "◫", title: "Analyze data", desc: "Find insights faster" },
];

function loadSavedChat() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return {
      messages: Array.isArray(saved.messages) ? saved.messages : [],
      conversationId: saved.conversationId || null,
    };
  } catch {
    return { messages: [], conversationId: null };
  }
}

export default function App() {
  const [savedChat] = useState(loadSavedChat);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState(savedChat.messages);
  const [conversationId, setConversationId] = useState(savedChat.conversationId);
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState("");

  const recognitionRef = useRef(null);
  const requestRef = useRef(null);
  const conversationIdRef = useRef(savedChat.conversationId);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ messages, conversationId })
    );
  }, [messages, conversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages, loading]);

  useEffect(() => {
    return () => {
      requestRef.current?.abort();
      recognitionRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, []);

  function newChat() {
    requestRef.current?.abort();
    requestRef.current = null;
    recognitionRef.current?.abort();
    window.speechSynthesis?.cancel();

    conversationIdRef.current = null;
    setMessages([]);
    setConversationId(null);
    setInput("");
    setError("");
    setLoading(false);
    setListening(false);
    localStorage.removeItem(STORAGE_KEY);
  }

  async function sendMessage(event) {
    event?.preventDefault();
    const text = input.trim();

    if (!text || requestRef.current) return;

    const controller = new AbortController();
    requestRef.current = controller;

    setInput("");
    setError("");
    setLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: text }]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          message: text,
          conversation_id: conversationIdRef.current,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Server error: ${response.status}`);
      }

      if (!data.ai_response) {
        throw new Error("Backend returned an empty response.");
      }

      if (requestRef.current !== controller) return;

      conversationIdRef.current = data.conversation_id;
      setConversationId(data.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.ai_response },
      ]);
    } catch (err) {
      if (err.name === "AbortError") return;
      if (requestRef.current !== controller) return;

      console.error("Hikari API error:", err);
      setError(
        err instanceof TypeError
          ? "Backend se connection nahi ho paaya. FastAPI check karo."
          : err.message || "Something went wrong."
      );
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null;
        setLoading(false);
      }
    }
  }

  function startVoice() {
    const Recognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!Recognition) {
      setError("Is browser mein speech recognition available nahi hai.");
      return;
    }

    if (listening) {
      recognitionRef.current?.stop();
      return;
    }

    const recognition = new Recognition();
    recognitionRef.current = recognition;
    recognition.lang = "en-IN";
    recognition.interimResults = false;

    recognition.onstart = () => {
      setListening(true);
      setError("");
    };

    recognition.onresult = (event) => {
      setInput(event.results[0][0].transcript);
    };

    recognition.onerror = (event) => {
      if (event.error !== "aborted") {
        setError(`Microphone error: ${event.error}`);
      }
    };

    recognition.onend = () => setListening(false);
    recognition.start();
  }

  function speak(text) {
    if (!window.speechSynthesis) {
      setError("Text-to-speech is not supported.");
      return;
    }

    window.speechSynthesis.cancel();

    const speech = new SpeechSynthesisUtterance(
      text
        .replace(/```[\s\S]*?```/g, "Code block.")
        .replace(/[#*_`~]/g, "")
    );

    speech.lang = "en-IN";
    speech.rate = 1;
    window.speechSynthesis.speak(speech);
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-symbol">✳</div>
          <div>
            <strong>HIKARI <span>AI</span></strong>
            <small>Your intelligent space</small>
          </div>
        </div>

        <button className="new-chat" onClick={newChat}>
          <span>＋</span> New chat
        </button>

        <div className="sidebar-label">WORKSPACE</div>
        <nav>
          <button className="nav-active">⌂ <span>Home</span></button>
          <button onClick={newChat}>☷ <span>Chat</span></button>
          <button disabled>◇ <span>AI Tools · Soon</span></button>
          <button disabled>◷ <span>Library · Soon</span></button>
          <button disabled>⚙ <span>Settings · Soon</span></button>
        </nav>

        <div className="sidebar-bottom">
          <div className="profile">
            <div className="profile-avatar">AI</div>
            <div>
              <strong>Personal Workspace</strong>
              <small>Local Qwen 2.5</small>
            </div>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <span>Workspace / Home</span>
          <div className="topbar-right">
            <span className="model-name">HIKARI · QWEN</span>
            <span className="profile-avatar small">AI</span>
          </div>
        </header>

        <div className="content">
          {messages.length === 0 ? (
            <>
              <div className="eyebrow">
                <span className="dot"></span> YOUR AI WORKSPACE
              </div>
              <h1>Make room for better ideas.</h1>
              <p className="intro">
                Your thoughts, our curiosity. Writing, coding,
                learning, and everything in between.
              </p>
            </>
          ) : (
            <div className="conversation">
              {messages.map((message, index) => (
                <div key={index} className={`message ${message.role}`}>
                  <div className="message-label">
                    {message.role === "user" ? "You" : "✳ Hikari AI"}
                  </div>

                  <div className="message-content">
                    {message.role === "assistant" ? (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.content}
                      </ReactMarkdown>
                    ) : (
                      <p>{message.content}</p>
                    )}
                  </div>

                  {message.role === "assistant" && (
                    <button
                      className="listen"
                      onClick={() => speak(message.content)}
                    >
                      ◖)) Listen
                    </button>
                  )}
                </div>
              ))}

              {loading && <p className="thinking">✳ Hikari is thinking...</p>}
              <div ref={messagesEndRef} />
            </div>
          )}

          <form className="prompt-box" onSubmit={sendMessage}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask Hikari anything..."
              rows={3}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
            />

            <div className="prompt-actions">
              <div className="prompt-left">
                <span className="model-chip">✧ Qwen 2.5</span>
                <button
                  type="button"
                  className="voice-btn"
                  onClick={startVoice}
                >
                  {listening ? "● Listening" : "♩ Voice"}
                </button>
              </div>

              <button
                type="submit"
                className="send-btn"
                disabled={loading || !input.trim()}
              >
                ↑
              </button>
            </div>
          </form>

          {error && <p className="error">{error}</p>}

          {messages.length === 0 && (
            <section className="ideas">
              <h2>Start with an idea</h2>
              <p>Explore, create, learn, and think better.</p>

              <div className="idea-grid">
                {ideas.map((item) => (
                  <button
                    className="idea-card"
                    key={item.title}
                    onClick={() =>
                      setInput(
                        item.title === "Write code"
                          ? "Help me write Python code"
                          : item.title === "Summarize"
                          ? "Help me summarize a topic"
                          : item.title === "Create images"
                          ? "Help me plan a creative image"
                          : "Explain how to analyze a dataset"
                      )
                    }
                  >
                    <div className="idea-icon">{item.icon}</div>
                    <strong>{item.title}</strong>
                    <small>{item.desc}</small>
                  </button>
                ))}
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  );
}
