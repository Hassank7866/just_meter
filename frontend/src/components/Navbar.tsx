import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { SystemStats } from '../api/client';
import {
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
} from 'lucide-react';

interface NavbarProps {
  activeTab: 'authorized' | 'spotted' | 'violations' | 'live-camera';
  setActiveTab: (tab: 'authorized' | 'spotted' | 'violations' | 'live-camera') => void;
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

          {/* Center: Minimalist Navigation Tabs */}
          <nav className="hidden md:flex items-center gap-1 bg-slate-950/70 p-1 rounded-xl border border-slate-800/90 shadow-inner">
            {/* Tab 1: Authorized Fleet */}
            <button
              onClick={() => setActiveTab('authorized')}
              className={`nav-tab !px-3 !py-1.5 !text-xs ${activeTab === 'authorized' ? 'active' : ''}`}
              title="Authorized Government Fleet Registry"
            >
              <ShieldCheck size={15} className={activeTab === 'authorized' ? 'text-sky-400' : 'text-slate-400'} />
              <span>Fleet</span>
              {stats && (
                <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                  activeTab === 'authorized' ? 'bg-sky-500/30 text-sky-200' : 'bg-slate-800 text-slate-400'
                }`}>
                  {stats.authorized_vehicles_count}
                </span>
              )}
            </button>

            {/* Tab 2: Spotted Vehicles */}
            <button
              onClick={() => setActiveTab('spotted')}
              className={`nav-tab !px-3 !py-1.5 !text-xs ${activeTab === 'spotted' ? 'active' : ''}`}
              title="Spotted Vehicles & Duty Verification Log"
            >
              <Eye size={15} className={activeTab === 'spotted' ? 'text-sky-400' : 'text-slate-400'} />
              <span>Spotted</span>
              {stats && stats.violations_count > 0 ? (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-rose-500/30 text-rose-300 border border-rose-500/40">
                  {stats.violations_count}
                </span>
              ) : stats ? (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              ) : null}
            </button>

            {/* Tab 3: Violations & E-Challans */}
            <button
              onClick={() => setActiveTab('violations')}
              className={`nav-tab !px-3 !py-1.5 !text-xs ${activeTab === 'violations' ? 'active' : ''}`}
              title="Violations & Official E-Challans"
            >
              <ShieldAlert size={15} className={activeTab === 'violations' ? 'text-rose-400' : 'text-rose-400/70'} />
              <span>Violations</span>
              {stats && stats.violations_count > 0 && (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-rose-600 text-white font-bold animate-pulse shadow-sm shadow-rose-600/50">
                  {stats.violations_count}
                </span>
              )}
            </button>

            {/* Tab 4: Live Camera Detection */}
            <button
              onClick={() => setActiveTab('live-camera')}
              className={`nav-tab !px-3 !py-1.5 !text-xs ${activeTab === 'live-camera' ? 'active !text-emerald-300' : ''}`}
              title="Live AI Camera Detection & Bounding Boxes"
            >
              <Camera size={15} className={activeTab === 'live-camera' ? 'text-emerald-400 animate-pulse' : 'text-emerald-400/80'} />
              <span>Live Camera</span>
              <span className="flex items-center gap-1 text-[9px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.2 rounded font-bold font-mono border border-emerald-500/30">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                LIVE
              </span>
            </button>
          </nav>

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
                      <span>Super Admin Role</span>
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

        {/* Mobile Navigation Tabs (visible on small screens below md) */}
        <div className="md:hidden flex items-center justify-around py-1.5 border-t border-slate-800/80 gap-1">
          <button
            onClick={() => setActiveTab('authorized')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'authorized' ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40' : 'text-slate-400'
            }`}
          >
            <ShieldCheck size={13} />
            <span>Fleet</span>
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
            onClick={() => setActiveTab('violations')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'violations' ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' : 'text-rose-400/70'
            }`}
          >
            <ShieldAlert size={13} />
            <span>Violations</span>
          </button>

          <button
            onClick={() => setActiveTab('live-camera')}
            className={`px-2 py-1 rounded-lg text-xs font-medium flex items-center gap-1 ${
              activeTab === 'live-camera' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'text-emerald-400/80 bg-emerald-950/30'
            }`}
          >
            <Camera size={13} className="text-emerald-400" />
            <span>Live AI</span>
          </button>
        </div>
      </div>
    </header>
  );
};
