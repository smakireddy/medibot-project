"use client";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { sendChat } from "@/lib/api";
import { ROLE_META, type Message, type Role, type SourceCitation } from "@/lib/types";

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [role, setRole]         = useState<Role>("nurse");
  const [username, setUsername] = useState("");
  const [token, setToken]       = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = localStorage.getItem("medibot_token");
    const r = localStorage.getItem("medibot_role") as Role;
    const u = localStorage.getItem("medibot_username");
    if (!t || !r) { router.replace("/login"); return; }
    setToken(t);
    setRole(r);
    setUsername(u || "");

    setMessages([{
      id: "welcome",
      type: "bot",
      text: `Hello! I'm MediBot. You're logged in as **${ROLE_META[r].label}**. You have access to: ${ROLE_META[r].collections.join(", ")} collections. How can I help you today?`,
      timestamp: new Date(),
    }]);
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function logout() {
    ["medibot_token", "medibot_role", "medibot_username"].forEach((k) => localStorage.removeItem(k));
    router.push("/login");
  }

  async function handleSend() {
    const q = input.trim();
    if (!q || loading) return;

    const userMsg: Message = { id: Date.now().toString(), type: "user", text: q, timestamp: new Date() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await sendChat(q, token);
      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        type: "bot",
        text: res.answer,
        sources: res.sources,
        retrieval_type: res.retrieval_type,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (e: unknown) {
      setMessages((prev) => [...prev, {
        id: (Date.now() + 1).toString(),
        type: "bot",
        text: `Error: ${e instanceof Error ? e.message : "Something went wrong"}`,
        timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
    }
  }

  const meta = ROLE_META[role];

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col p-4 shrink-0">
        <div className="mb-6">
          <div className="text-2xl font-bold text-indigo-700 mb-1">🏥 MediBot</div>
          <div className="text-xs text-gray-400">MediAssist Health Network</div>
        </div>

        {/* Role badge */}
        <div className={`rounded-xl px-4 py-3 mb-4 ${meta.bg}`}>
          <div className="text-xs font-medium text-gray-500 mb-1">Signed in as</div>
          <div className={`font-semibold ${meta.color}`}>{username}</div>
          <div className={`text-sm font-bold ${meta.color}`}>{meta.label}</div>
        </div>

        {/* Collections */}
        <div className="mb-4">
          <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Your Collections</div>
          <div className="space-y-1">
            {meta.collections.map((col) => (
              <div key={col} className="flex items-center gap-2 text-sm text-gray-600">
                <span className="w-2 h-2 rounded-full bg-indigo-400 shrink-0" />
                {col}
              </div>
            ))}
          </div>
        </div>

        <div className="mt-auto">
          <button
            onClick={logout}
            className="w-full text-sm text-gray-500 hover:text-red-500 border border-gray-200 rounded-lg py-2 transition"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main chat area */}
      <main className="flex flex-col flex-1 min-w-0">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-3">
          <span className="font-semibold text-gray-700">Chat</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${meta.bg} ${meta.color}`}>
            {meta.label}
          </span>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} msg={msg} />
          ))}
          {loading && (
            <div className="flex gap-2 items-center text-gray-400 text-sm pl-2">
              <span className="animate-pulse">●</span>
              <span className="animate-pulse delay-75">●</span>
              <span className="animate-pulse delay-150">●</span>
              <span className="ml-1">MediBot is thinking…</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="bg-white border-t border-gray-200 px-6 py-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
              placeholder="Ask a question…"
              disabled={loading}
              className="flex-1 border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 disabled:bg-gray-50"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-semibold px-5 rounded-xl transition disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  if (msg.type === "user") {
    return (
      <div className="flex justify-end">
        <div className="bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 max-w-lg text-sm">
          {msg.text}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 max-w-2xl shadow-sm w-full">
        {/* Retrieval type badge */}
        {msg.retrieval_type && (
          <div className="mb-2">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
              msg.retrieval_type === "sql_rag"
                ? "bg-amber-100 text-amber-700"
                : "bg-teal-100 text-teal-700"
            }`}>
              {msg.retrieval_type === "sql_rag" ? "SQL RAG" : "Hybrid RAG"}
            </span>
          </div>
        )}

        {/* Answer text — render ** as bold */}
        <div className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
          {msg.text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
            part.startsWith("**") && part.endsWith("**")
              ? <strong key={i}>{part.slice(2, -2)}</strong>
              : part
          )}
        </div>

        {/* Source citations */}
        {msg.sources && msg.sources.length > 0 && (
          <Sources sources={msg.sources} />
        )}
      </div>
    </div>
  );
}

function Sources({ sources }: { sources: SourceCitation[] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3 border-t border-gray-100 pt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-indigo-500 hover:text-indigo-700 font-medium"
      >
        {open ? "▾" : "▸"} {sources.length} source{sources.length !== 1 ? "s" : ""}
      </button>
      {open && (
        <div className="mt-2 space-y-1.5">
          {sources.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-gray-500 bg-gray-50 rounded-lg px-3 py-2">
              <span className="text-indigo-400 font-bold shrink-0">[{i + 1}]</span>
              <div>
                <span className="font-medium text-gray-700">{s.source_document}</span>
                {s.section_title && <span className="mx-1 text-gray-300">·</span>}
                {s.section_title && <span>{s.section_title}</span>}
                <span className={`ml-2 px-1.5 py-0.5 rounded text-xs font-medium bg-gray-200 text-gray-600`}>
                  {s.collection}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
