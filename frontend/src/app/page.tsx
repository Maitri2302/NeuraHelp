"use client";
import { useState, useEffect } from "react";
import Sidebar from "../components/Sidebar";
import ChatTab from "../components/ChatTab";
import UploadModal from "../components/UploadModal";
import SearchModal from "../components/SearchModal";
import AuthScreen from "../components/AuthScreen";

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isChecking, setIsChecking] = useState(true);
  
  // Modals and Shared State
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showSearchModal, setShowSearchModal] = useState(false);
  const [documents, setDocuments] = useState<{ filename: string; size: number; summary?: string }[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const fetchDocuments = async () => {
    setIsLoadingDocs(true);
    try {
      const token = localStorage.getItem("token");
      if (!token) return;
      const res = await fetch(`${API_BASE}/api/documents`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoadingDocs(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      setIsAuthenticated(true);
    }
    setIsChecking(false);
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      fetchDocuments();
    }
  }, [isAuthenticated]);

  const handleLogin = (token: string, username: string) => {
    localStorage.setItem("token", token);
    localStorage.setItem("username", username);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("username");
    setIsAuthenticated(false);
  };

  const handleDeleteDoc = async (filename: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(filename)}`, {
        method: "DELETE",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        fetchDocuments();
      }
    } catch (e) {
      console.error("Failed to delete", e);
    }
  };

  if (isChecking) {
    return <div className="h-screen flex items-center justify-center bg-slate-900 text-slate-100 animate-pulse font-medium">Loading NeuraDesk...</div>;
  }

  if (!isAuthenticated) {
    return <AuthScreen onLogin={handleLogin} />;
  }

  return (
    <div className="flex h-screen overflow-hidden bg-slate-900 text-slate-100">
      {/* Persistent Sidebar */}
      <Sidebar 
        onLogout={handleLogout} 
        onUploadClick={() => setShowUploadModal(true)}
        onSearchClick={() => setShowSearchModal(true)}
        documents={documents}
        isLoadingDocs={isLoadingDocs}
        onRefreshDocs={fetchDocuments}
        onDeleteDoc={handleDeleteDoc}
      />

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col h-full relative z-10 bg-slate-900/50 backdrop-blur-3xl">
        <ChatTab />
      </main>

      {/* Overlays */}
      {showUploadModal && (
        <UploadModal 
          onClose={() => setShowUploadModal(false)} 
          onUploadSuccess={() => {
            fetchDocuments();
          }}
        />
      )}
      {showSearchModal && (
        <SearchModal 
          onClose={() => setShowSearchModal(false)} 
          documents={documents} 
        />
      )}
    </div>
  );
}
