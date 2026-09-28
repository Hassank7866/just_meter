import React, { useState, useEffect } from 'react';
import { SystemStats } from '../api/client';
import { Clock, RefreshCw, Activity, ShieldAlert, Car } from 'lucide-react';

interface HeaderProps {
  activeTab: 'authorized' | 'spotted';
  stats: SystemStats | null;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({ activeTab, stats, onRefresh, isRefreshing }) => {
  const [timeString, setTimeString] = useState<string>('');

  useEffect(() => {
    const updateClock = () => {
      const now = new Date();
      setTimeString(
        now.toLocaleTimeString('en-PK', {
          timeZone: 'Asia/Karachi',
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
          hour12: true,
        })
      );
    };
    updateClock();
    const interval = setInterval(updateClock, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="h-16 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Active Page Indicator */}
      <div className="flex items-center gap-3">
        <h2 className="text-base font-bold text-white tracking-wide flex items-center gap-2">
          {activeTab === 'authorized' ? (
            <>
              <Car className="text-sky-400" size={20} />
              <span>Authorized Fleet Registry</span>
            </>
          ) : (
            <>
              <ShieldAlert className="text-amber-400" size={20} />
              <span>Government Vehicles Spotted & Evidence</span>
            </>
          )}
        </h2>
      </div>

      {/* Right Telemetry & Controls */}
      <div className="flex items-center gap-4 text-xs">
        {/* Quick Stats Badges */}
        {stats && (
          <div className="hidden md:flex items-center gap-3 bg-slate-950/60 py-1.5 px-3 rounded-lg border border-slate-800">
            <div className="flex items-center gap-1.5 text-slate-300">
              <span className="text-slate-400">Fleet:</span>
              <span className="font-mono font-bold text-sky-400">{stats.authorized_vehicles_count}</span>
            </div>
            <span className="w-1 h-3 bg-slate-700 rounded-full"></span>
            <div className="flex items-center gap-1.5 text-slate-300">
              <span className="text-slate-400">Sightings:</span>
              <span className="font-mono font-bold text-slate-200">{stats.total_government_sightings}</span>
            </div>
            <span className="w-1 h-3 bg-slate-700 rounded-full"></span>
            <div className="flex items-center gap-1.5 text-slate-300">
              <span className="text-slate-400">Violations:</span>
              <span className="font-mono font-bold text-rose-400">{stats.violations_count}</span>
            </div>
          </div>
        )}

        {/* Live Clock (Asia/Karachi) */}
        <div className="flex items-center gap-1.5 bg-slate-800/80 text-sky-300 py-1.5 px-3 rounded-lg border border-slate-700/60 font-mono">
          <Clock size={14} className="text-sky-400" />
          <span>{timeString || 'PKT'}</span>
        </div>

        {/* System Active Status */}
        <div className="flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 py-1.5 px-2.5 rounded-lg">
          <Activity size={13} className="animate-pulse" />
          <span className="font-semibold text-[11px]">ONLINE</span>
        </div>

        {/* Refresh Button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="btn-secondary py-1.5 px-2.5 rounded-lg text-xs"
          title="Refresh Data"
        >
          <RefreshCw size={14} className={isRefreshing ? 'animate-spin text-sky-400' : ''} />
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>
    </header>
  );
};
