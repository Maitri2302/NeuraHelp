"use client";
import { useState, useEffect } from "react";

interface SidebarProps {
  onLogout: () => void;
  onUploadClick: () => void;
  onSearchClick: () => void;
  documents: { filename: string; size: number; summary?: string }[];
  isLoadingDocs: boolean;
  onRefreshDocs: () => void;
  onDeleteDoc: (filename: string) => void;
}

export default function Sidebar({ 
  onLogout, 
  onUploadClick, 
  onSearchClick,
  documents,
  isLoadingDocs,
  onRefreshDocs,
  onDeleteDoc
}: SidebarProps) {
  const [username, setUsername] = useState("User");

  useEffect(() => {
    setUsername(localStorage.getItem("username") || "User");
  }, []);

  return (
    <div className="w-72 h-screen glass-panel flex flex-col border-r border-slate-800/50 relative z-20">
      {/* Brand */}
      <div className="p-6 flex items-center gap-3 border-b border-slate-700/50">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white font-bold shadow-lg shadow-indigo-500/20">
          N
        </div>
        <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-violet-400 bg-clip-text text-transparent">
          NeuraDesk
        </h1>
      </div>

      {/* Main Actions */}
      <div className="p-4 space-y-2">
        <button 
          onClick={onUploadClick}
          className="w-full flex items-center gap-3 px-4 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition-all shadow-md shadow-indigo-900/20 group"
        >
          <svg className="w-5 h-5 text-indigo-200 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
          <span className="font-semibold">Upload Document</span>
        </button>

        <button 
          onClick={onSearchClick}
          className="w-full flex items-center gap-3 px-4 py-3 bg-slate-800/50 hover:bg-slate-700 text-slate-200 rounded-xl transition-all border border-slate-700/50"
        >
          <svg className="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
          <span className="font-medium">Semantic Search</span>
        </button>
      </div>

      {/* Knowledge Base List */}
      <div className="flex-1 overflow-y-auto px-4 py-2 mt-2">
        <div className="flex items-center justify-between mb-3 px-1">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">Knowledge Base</h3>
          <button onClick={onRefreshDocs} className="text-slate-500 hover:text-indigo-400 transition-colors" title="Refresh">
            <svg className={`w-4 h-4 ${isLoadingDocs ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          </button>
        </div>

        {isLoadingDocs && documents.length === 0 ? (
          <div className="text-center py-4 text-sm text-slate-500 animate-pulse">Loading...</div>
        ) : documents.length === 0 ? (
          <div className="text-center py-6 px-4 bg-slate-800/30 rounded-xl border border-dashed border-slate-700/50 text-sm text-slate-500">
            No documents yet.
          </div>
        ) : (
          <div className="space-y-2">
            {documents.map(doc => (
              <div key={doc.filename} className="group flex flex-col p-3 bg-slate-800/40 hover:bg-slate-700/60 rounded-xl border border-transparent hover:border-slate-600/50 transition-all cursor-default">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 overflow-hidden">
                    <svg className="w-4 h-4 text-indigo-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                    <span className="text-sm font-medium text-slate-300 truncate">{doc.filename}</span>
                  </div>
                  <button 
                    onClick={() => onDeleteDoc(doc.filename)}
                    className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
                    title="Delete"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  </button>
                </div>
                {doc.summary && (
                  <div className="mt-2 text-xs text-slate-400 line-clamp-3 leading-relaxed pl-7">
                    {doc.summary}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* User Profile Footer */}
      <div className="p-4 border-t border-slate-700/50 bg-slate-900/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-300 flex-shrink-0">
              {username.charAt(0).toUpperCase()}
            </div>
            <span className="text-sm font-medium text-slate-300 truncate">{username}</span>
          </div>
          <button 
            onClick={onLogout}
            className="p-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
            title="Sign out"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></svg>
          </button>
        </div>
      </div>
    </div>
  );
}
