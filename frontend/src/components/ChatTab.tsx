"use client";
import { useState, useRef, useEffect } from "react";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ChatTab() {
  const [messages, setMessages] = useState<{ role: "user" | "ai"; content: string }[]>([]);
  const [query, setQuery] = useState("");
  const [loadingChat, setLoadingChat] = useState(false);
  const [sessions, setSessions] = useState<{id: string, title: string}[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>("default");
  const bottomRef = useRef<HTMLDivElement>(null);
  
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    fetchSessions();
    loadSession("default");
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loadingChat]);

  const fetchSessions = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/chat/sessions`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const loadSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/chat/history/${sessionId}`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.history || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const startNewChat = () => {
    setCurrentSessionId(Math.random().toString(36).substring(2, 9));
    setMessages([]);
  };

  const deleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to permanently delete this chat session?")) return;
    
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/chat/history/${sessionId}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.id !== sessionId));
        if (currentSessionId === sessionId) {
          startNewChat();
        }
      }
    } catch (e) {
      console.error("Failed to delete session", e);
    }
  };

  const handleChatSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userMessage = { role: "user" as const, content: query };
    setMessages((prev) => [...prev, userMessage]);
    setQuery("");
    setLoadingChat(true);
    
    // Add empty AI message to be populated via stream
    setMessages((prev) => [...prev, { role: "ai", content: "" }]);

    try {
      const token = localStorage.getItem("token");
      const response = await fetch(`${API_BASE}/api/chat/stream`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}` 
        },
        body: JSON.stringify({ query: userMessage.content, session_id: currentSessionId }),
      });

      if (!response.ok) throw new Error("Failed to fetch response");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder("utf-8");
      
      if (!reader) return;
      
      let done = false;
      let buffer = "";
      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || ""; // Keep the last incomplete line in the buffer
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') {
                done = true;
                break;
              }
              try {
                const parsed = JSON.parse(data);
                if (parsed.content) {
                  setMessages((prev) => {
                    const newMessages = [...prev];
                    const lastIndex = newMessages.length - 1;
                    // Deep copy the last message to avoid React Strict Mode double mutation
                    newMessages[lastIndex] = {
                      ...newMessages[lastIndex],
                      content: newMessages[lastIndex].content + parsed.content
                    };
                    return newMessages;
                  });
                }
              } catch (e) {
                // Ignore parse errors
              }
            }
          }
        }
      }
      
      // Refresh sessions list if it's a new chat
      if (!sessions.find(s => s.id === currentSessionId)) {
        fetchSessions();
      }
      
    } catch (error) {
      console.error(error);
      setMessages((prev) => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1].content = "Error connecting to backend.";
        return newMessages;
      });
    } finally {
      setLoadingChat(false);
    }
  };

  // Pre-process AI text so citations become Markdown links
  const processContentForMarkdown = (content: string) => {
    return content.replace(/\[([^\]]+?\.[a-zA-Z0-9]+)\](?!\()/g, '[$1](cite:$1)');
  };

  return (
    <div className="flex h-full w-full max-w-[1400px] mx-auto gap-4 px-4 sm:px-6">
      
      {/* Sessions Sidebar Column */}
      <div className="w-64 shrink-0 flex flex-col py-6 border-r border-slate-800/50 pr-4">
        <button 
          onClick={startNewChat}
          className="w-full bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 border border-indigo-500/30 rounded-xl py-3 px-4 font-semibold text-sm transition-all flex items-center justify-center gap-2 mb-6"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          New Chat
        </button>
        
        <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3 px-2">Recent Chats</h3>
        
        <div className="flex-1 overflow-y-auto custom-scrollbar flex flex-col gap-1 pr-1">
          {sessions.length === 0 && (
            <div className="text-slate-500 text-sm italic px-2">No past sessions found.</div>
          )}
          {sessions.map((session) => (
            <div key={session.id} className={`group relative w-full flex items-center justify-between px-3 py-2 rounded-lg text-[13px] font-medium transition-all ${
              currentSessionId === session.id 
                ? "bg-slate-800 text-indigo-300 shadow-sm" 
                : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
            }`}>
              <button
                onClick={() => loadSession(session.id)}
                className="flex items-center gap-2 flex-1 truncate text-left"
              >
                <svg className="w-4 h-4 shrink-0 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                <span className="truncate">{session.title}</span>
              </button>
              
              <button 
                onClick={(e) => deleteSession(e, session.id)}
                className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-500/20 text-slate-500 hover:text-red-400 rounded-md transition-all shrink-0"
                title="Delete Chat"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex flex-col h-full flex-1 relative min-w-0">
        <div className="flex-1 overflow-y-auto py-8 pr-2 flex flex-col gap-6 custom-scrollbar">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-slate-500 animate-fade-in-up">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-500/20 flex items-center justify-center text-indigo-400 mb-6 border border-indigo-500/20">
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
              </div>
              <h2 className="text-3xl font-bold text-slate-200 mb-3 tracking-tight">How can I help you today?</h2>
              <p className="text-slate-400">Ask questions about your uploaded documents.</p>
            </div>
          )}
          
          {messages.map((msg, index) => (
            <div key={index} className={`flex w-full animate-fade-in-up ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "ai" && (
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold mr-4 mt-1 shadow-md shadow-indigo-500/20 shrink-0">
                  AI
                </div>
              )}
              <div className={`max-w-[85%] rounded-3xl px-6 py-4 ${
                msg.role === "user" 
                  ? "bg-indigo-600 text-white rounded-br-sm shadow-md shadow-indigo-900/20" 
                  : "bg-slate-800/80 text-slate-200 border border-slate-700/50 rounded-tl-sm shadow-sm prose prose-invert prose-indigo max-w-none"
                }`}
              >
                {msg.role === "user" ? (
                  <div className="text-[15px] whitespace-pre-wrap leading-relaxed font-medium">{msg.content}</div>
                ) : (
                  <div className="text-[15px] leading-relaxed">
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                      components={{
                      a: ({node, href, children, ...props}) => {
                        if (href?.startsWith('cite:')) {
                          const filename = href.replace('cite:', '');
                          return (
                            <span className="inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 mx-1 align-middle whitespace-nowrap shadow-sm">
                              <svg className="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                              {filename}
                            </span>
                          );
                        }
                        return <a href={href} target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:underline" {...props}>{children}</a>;
                      },
                      p: ({node, children}) => <p className="mb-4 last:mb-0 leading-relaxed">{children}</p>,
                      h1: ({node, children}) => <h1 className="text-2xl font-bold mt-6 mb-4 text-slate-100">{children}</h1>,
                      h2: ({node, children}) => <h2 className="text-xl font-bold mt-5 mb-3 text-slate-100">{children}</h2>,
                      h3: ({node, children}) => <h3 className="text-lg font-semibold mt-4 mb-2 text-slate-200">{children}</h3>,
                      ul: ({node, children}) => <ul className="list-disc pl-6 mb-4 space-y-1">{children}</ul>,
                      ol: ({node, children}) => <ol className="list-decimal pl-6 mb-4 space-y-1">{children}</ol>,
                      li: ({node, children}) => <li className="pl-1">{children}</li>,
                      strong: ({node, children}) => <strong className="font-semibold text-slate-100">{children}</strong>,
                      blockquote: ({node, children}) => <blockquote className="border-l-4 border-indigo-500/50 pl-4 py-1 italic text-slate-400 bg-slate-900/30 rounded-r-lg my-4">{children}</blockquote>,
                      pre: ({node, children}) => <pre className="bg-slate-900 p-4 rounded-xl overflow-x-auto border border-slate-700/50 my-5 shadow-inner">{children}</pre>,
                      code: ({node, className, children, ...props}) => {
                        const match = /language-(\w+)/.exec(className || '')
                        const isInline = !match && !className?.includes('language-');
                        return isInline ? (
                          <code className="bg-slate-900/50 px-1.5 py-0.5 rounded text-indigo-300 text-[13px] font-mono border border-slate-700/30" {...props}>{children}</code>
                        ) : (
                          <code className={`text-sm text-slate-300 font-mono ${className}`} {...props}>{children}</code>
                        )
                      }
                    }}
                  >
                    {processContentForMarkdown(msg.content)}
                  </ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
          ))}
          
          {loadingChat && messages[messages.length - 1]?.content === "" && (
            <div className="flex justify-start items-end animate-fade-in-up">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold mr-4 shadow-md shadow-indigo-500/20 shrink-0">
                AI
              </div>
              <div className="bg-slate-800/80 shadow-sm border border-slate-700/50 rounded-3xl rounded-tl-sm px-6 py-5 flex gap-1.5 items-center max-w-[85%] min-w-[120px]">
                <div className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2.5 h-2.5 bg-indigo-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2.5 h-2.5 bg-indigo-300 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          )}
          <div ref={bottomRef} className="h-4" />
        </div>
        
        {/* Input Area */}
        <div className="w-full pb-6 pt-2 sticky bottom-0 z-40 bg-slate-900/95 backdrop-blur-md">
          <div className="absolute top-0 left-0 w-full h-12 -mt-12 bg-gradient-to-t from-slate-900/95 to-transparent pointer-events-none"></div>
          
          <form onSubmit={handleChatSubmit} className="relative flex items-center group shadow-lg">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              disabled={loadingChat}
              placeholder="Message NeuraDesk..."
              className="w-full bg-slate-800 border border-slate-700 focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/10 rounded-2xl pl-6 pr-16 py-4 text-slate-100 placeholder-slate-500 transition-all disabled:opacity-50 outline-none text-[15px]"
            />
            <button
              type="submit"
              disabled={loadingChat || !query.trim()}
              className="absolute right-3 p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl hover:scale-105 transition-all disabled:opacity-50 shadow-md shadow-indigo-500/20 active:scale-95"
            >
              <svg className="w-5 h-5 translate-x-[-1px]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
            </button>
          </form>
          <div className="text-center mt-3">
            <span className="text-[11px] text-slate-500 font-medium">NeuraDesk can make mistakes. Verify important information.</span>
          </div>
        </div>
      </div>
    </div>
  );
}
