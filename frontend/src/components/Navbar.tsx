import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { SystemStats } from '../api/client';
import {
  LayoutDashboard,
  ShieldCheck,
  Eye,
  Camera,
  Radio,
  RefreshCw,
  LogOut,
  User,
  ShieldAlert,
  ChevronDown,
  MessageSquare,
  Settings,
  ScanLine,
  Archive,
  MapPin,
} from 'lucide-react';

export type AppTab = 'users' | 'reports' | 'audit' | 'dashboard' | 'vims' | 'digital-twin' | 'challans' | 'authorized' | 'spotted' | 'anpr-review' | 'evidence' | 'geofences' | 'violations' | 'live-camera';

interface NavbarProps {
  activeTab: AppTab;
  setActiveTab: (tab: AppTab) => void;
  stats: SystemStats | null;
  onRefresh: () => void;
  isRefreshing: boolean;
  onOpenWhatsAppSettings?: () => void;
  isWhatsAppConfigured?: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  stats,
  onRefresh,
  isRefreshing,
  onOpenWhatsAppSettings,
  isWhatsAppConfigured,
}) => {
  const { user, logout } = useAuth();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur-xl border-b border-slate-800/90 shadow-md shadow-black/20 w-full max-w-full">
      <div className="max-w-7xl mx-auto px-3 sm:px-6">
        <div className="flex items-center justify-between h-13 py-2 gap-2 sm:gap-4">
          {/* Left: Brand / Logo */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center shadow-md shadow-sky-500/20 border border-sky-400/30 shrink-0">
              <Radio className="text-white" size={16} />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-sm sm:text-base tracking-wider text-white whitespace-nowrap">
                JUST <span className="text-sky-400">METER</span>
              </span>
              <span className="hidden xl:inline text-[11px] text-slate-400 font-medium pl-2 border-l border-slate-700/80">
                AJK Government Car Surveillance System
              </span>
            </div>
          </div>

          {/* Right: Actions (WhatsApp, Refresh, Admin Dropdown) */}
          <div className="flex items-center gap-2 shrink-0">
            {/* WhatsApp Cloud API Config Button */}
            {onOpenWhatsAppSettings && (
              <button
                onClick={onOpenWhatsAppSettings}
                className={`h-8 px-2 sm:px-2.5 text-xs rounded-lg flex items-center gap-1.5 transition-all border ${
                  isWhatsAppConfigured
                    ? 'bg-emerald-950/40 hover:bg-emerald-900/50 border-emerald-500/30 text-emerald-300'
                    : 'bg-amber-500/10 hover:bg-amber-500/20 border-amber-500/30 text-amber-300'
                }`}
                title={isWhatsAppConfigured ? 'Meta WhatsApp Cloud API Active' : 'Configure WhatsApp Cloud API'}
              >
                <MessageSquare size={14} className={isWhatsAppConfigured ? 'text-emerald-400' : 'text-amber-400'} />
                <span className="hidden lg:inline text-[11px] font-medium">WhatsApp</span>
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isWhatsAppConfigured ? 'bg-emerald-400 shadow-sm shadow-emerald-400/50' : 'bg-amber-400 animate-ping'
                  }`}
                />
              </button>
            )}

            {/* Refresh Button */}
            <button
              onClick={onRefresh}
              disabled={isRefreshing}
              className="h-8 w-8 flex items-center justify-center rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700/70 text-slate-300 hover:text-white transition-all disabled:opacity-50"
              title="Refresh Live Data"
            >
              <RefreshCw size={14} className={isRefreshing ? 'animate-spin text-sky-400' : ''} />
            </button>

            {/* Admin User Avatar & Sign Out Dropdown */}
            <div className="relative">
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="h-8 flex items-center gap-1.5 px-2 rounded-lg bg-slate-800/80 hover:bg-slate-800 border border-slate-700/70 text-slate-200 transition-all"
              >
                <div className="w-5 h-5 rounded-md bg-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-[10px] border border-sky-500/30">
                  <User size={12} />
                </div>
                <span className="hidden xl:inline text-xs font-medium text-slate-200 max-w-[100px] truncate">
                  {user?.name || 'Admin'}
                </span>
                <ChevronDown size={12} className="text-slate-400" />
              </button>

              {/* Dropdown Menu */}
              {isDropdownOpen && (
                <>
                  <div
                    className="fixed inset-0 z-40"
                    onClick={() => setIsDropdownOpen(false)}
                  ></div>
                  <div className="absolute right-0 mt-2 w-56 rounded-xl bg-slate-900 border border-slate-800 shadow-2xl p-2 z-50 animate-fade-in">
                    <div className="px-3 py-2 border-b border-slate-800 mb-1">
                      <p className="text-xs font-semibold text-white truncate">{user?.name || 'System Admin'}</p>
                      <p className="text-[11px] text-slate-400 truncate">{user?.email || 'admin@justmeter.gov'}</p>
                    </div>
                    <div className="px-3 py-1.5 text-[11px] text-slate-400 flex items-center gap-1.5">
                      <ShieldAlert size={13} className="text-emerald-400" />
                      <span>{user?.role || 'Authenticated User'}</span>
                    </div>
                    {onOpenWhatsAppSettings && (
                      <button
                        onClick={() => {
                          setIsDropdownOpen(false);
                          onOpenWhatsAppSettings();
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-slate-200 hover:text-emerald-300 hover:bg-slate-800/80 transition-all text-left"
                      >
                        <Settings size={14} className="text-emerald-400" />
                        <span>WhatsApp API Settings</span>
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setIsDropdownOpen(false);
                        logout();
                      }}
                      className="w-full mt-1 flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium text-rose-300 hover:text-white hover:bg-rose-500/20 transition-all text-left"
                    >
                      <LogOut size={14} />
                      <span>Sign Out</span>
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>

        {/* Scrollable navigation keeps every module accessible at all widths. */}
        <nav aria-label="Main navigation" className="flex items-center justify-start overflow-x-auto overscroll-x-contain py-1.5 border-t border-slate-800/80 gap-1 scrollbar-visible">
          {(['reports', ...(['Administrator', 'Auditor', 'Supervisory Officer'].includes(user?.role || '') ? ['audit'] : []), ...(user?.role === 'Administrator' ? ['users'] : [])] as AppTab[]).map(tab => <button key={tab} onClick={() => setActiveTab(tab)} className={`shrink-0 px-2 py-1 rounded-lg text-xs font-medium ${activeTab === tab ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'text-slate-400'}`}>{tab === 'users' ? 'User access' : tab === 'reports' ? 'Reports' : 'Audit'}</button>)}
          {user?.role !== 'Auditor' && <>
          {user?.role === 'Administrator' && <button onClick={() => setActiveTab('vims')} className={`shrink-0 px-2 py-1 rounded-lg text-xs font-medium ${activeTab === 'vims' ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'text-slate-400'}`}>VIMS</button>}
          <button
            onClick={() => setActiveTab('dashboard')}
            className={`shrink-0 px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${activeTab === 'dashboard' ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'text-slate-400'}`}
          >
            <LayoutDashboard size={13} />
            <span>Overview</span>
          </button>
          <button
            onClick={() => setActiveTab('authorized')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'authorized' ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'text-slate-400'
            }`}
          >
            <ShieldCheck size={13} />
            <span>Fleet</span>
            {stats && <span className="text-[10px] text-slate-400">{stats.authorized_vehicles_count}</span>}
          </button>

          <button onClick={() => setActiveTab('digital-twin')}
            className={`shrink-0 px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${activeTab === 'digital-twin' ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'text-slate-400'}`}>
            <User size={13} /><span>Digital Twin</span>
          </button>
          <button onClick={() => setActiveTab('challans')}
            className={`shrink-0 px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${activeTab === 'challans' ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'text-slate-400'}`}>
            <Archive size={13} /><span>Challans</span>
          </button>

          <button
            onClick={() => setActiveTab('spotted')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'spotted' ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'text-slate-400'
            }`}
          >
            <Eye size={13} />
            <span>Spotted</span>
          </button>

          <button
            onClick={() => setActiveTab('anpr-review')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'anpr-review' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400'
            }`}
          >
            <ScanLine size={13} />
            <span>ANPR</span>
          </button>

          <button
            onClick={() => setActiveTab('evidence')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'evidence' ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40' : 'text-slate-400'
            }`}
          >
            <Archive size={13} />
            <span>Evidence</span>
          </button>

          {user?.role === 'Administrator' && <button
            onClick={() => setActiveTab('geofences')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${activeTab === 'geofences' ? 'bg-violet-500/20 text-violet-300 border border-violet-500/40' : 'text-violet-400/70'}`}
          >
            <MapPin size={13} />
            <span>Zones</span>
          </button>}

          <button
            onClick={() => setActiveTab('violations')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'violations' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'text-rose-400/70'
            }`}
          >
            <ShieldAlert size={13} />
            <span>Violations</span>
            {!!stats?.violations_count && <span className="text-[10px] text-rose-300">{stats.violations_count}</span>}
          </button>

          {user?.role === 'Administrator' && <button
            onClick={() => setActiveTab('live-camera')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'live-camera' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'text-emerald-400/80 bg-emerald-950/30'
            }`}
          >
            <Camera size={13} className="text-emerald-400" />
            <span>Live AI</span>
          </button>}
          </>}
        </nav>
      </div>
    </header>
  );
};
