import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  ShieldCheck,
  Eye,
  Camera,
  Layers,
  BarChart3,
  Settings,
  LogOut,
  Radio,
  UserCheck,
} from 'lucide-react';

interface SidebarProps {
  activeTab: 'authorized' | 'spotted';
  setActiveTab: (tab: 'authorized' | 'spotted') => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, setActiveTab }) => {
  const { user, logout } = useAuth();

  return (
    <aside className="w-64 bg-slate-900/90 border-r border-slate-800/80 flex flex-col justify-between h-screen sticky top-0 shrink-0 select-none z-30">
      {/* Brand Header */}
      <div>
        <div className="p-5 border-b border-slate-800 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20 border border-sky-400/30">
            <Radio className="text-white animate-pulse" size={22} />
          </div>
          <div>
            <h1 className="font-bold text-base tracking-wider text-white flex items-center gap-1.5">
              JUST <span className="text-sky-400">METER</span>
            </h1>
            <p className="text-[10px] text-slate-400 font-medium tracking-wide">
              AJK Government Car Surveillance System
            </p>
          </div>
        </div>

        {/* Navigation Section */}
        <div className="p-3 space-y-1 mt-2">
          <div className="px-3 py-1.5 text-[10px] font-bold text-slate-400 tracking-wider uppercase">
            Core Dashboards
          </div>

          {/* Page 1: Authorized Vehicles */}
          <button
            onClick={() => setActiveTab('authorized')}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
              activeTab === 'authorized'
                ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30 shadow-sm shadow-sky-900/20'
                : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-3">
              <ShieldCheck size={18} className={activeTab === 'authorized' ? 'text-sky-400' : 'text-slate-400'} />
              <span>Authorized Fleet</span>
            </div>
            <span className="text-[10px] bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded font-mono">
              CRUD
            </span>
          </button>

          {/* Page 2: Spotted Government Vehicles */}
          <button
            onClick={() => setActiveTab('spotted')}
            className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
              activeTab === 'spotted'
                ? 'bg-sky-500/15 text-sky-400 border border-sky-500/30 shadow-sm shadow-sky-900/20'
                : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-3">
              <Eye size={18} className={activeTab === 'spotted' ? 'text-sky-400' : 'text-slate-400'} />
              <span>Govt. Spotted Log</span>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
          </button>

          {/* Live Phone Camera link */}
          <a
            href="/"
            target="_blank"
            rel="noreferrer"
            className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-medium text-slate-300 hover:bg-slate-800/60 hover:text-sky-300 transition-all group"
          >
            <div className="flex items-center gap-3">
              <Camera size={18} className="text-amber-400 group-hover:scale-110 transition-transform" />
              <span>Phone Camera View</span>
            </div>
            <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded font-medium">
              Live
            </span>
          </a>

          {/* Upcoming 6-page slots */}
          <div className="pt-4 px-3 py-1.5 text-[10px] font-bold text-slate-400 tracking-wider uppercase">
            Extended Fleet Modules
          </div>

          <div className="opacity-50 cursor-not-allowed">
            <div className="w-full flex items-center justify-between px-3.5 py-2 rounded-xl text-xs text-slate-400">
              <div className="flex items-center gap-3">
                <Layers size={16} />
                <span>Global Detections</span>
              </div>
              <span className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">Upcoming</span>
            </div>

            <div className="w-full flex items-center justify-between px-3.5 py-2 rounded-xl text-xs text-slate-400">
              <div className="flex items-center gap-3">
                <BarChart3 size={16} />
                <span>Compliance Analytics</span>
              </div>
              <span className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">Upcoming</span>
            </div>

            <div className="w-full flex items-center justify-between px-3.5 py-2 rounded-xl text-xs text-slate-400">
              <div className="flex items-center gap-3">
                <Settings size={16} />
                <span>System & AI Settings</span>
              </div>
              <span className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded">Upcoming</span>
            </div>
          </div>
        </div>
      </div>

      {/* Admin Profile & Status Footer */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/40">
        <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 flex items-center justify-between mb-2">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-xs shrink-0 border border-sky-500/30">
              <UserCheck size={16} />
            </div>
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-white truncate">{user?.name || 'Admin User'}</p>
              <p className="text-[10px] text-slate-400 truncate">{user?.email || 'admin@justmeter.gov'}</p>
            </div>
          </div>
        </div>

        <button
          onClick={logout}
          className="w-full flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-xs font-medium text-rose-300 hover:text-white bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/20 transition-all"
        >
          <LogOut size={14} />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  );
};
