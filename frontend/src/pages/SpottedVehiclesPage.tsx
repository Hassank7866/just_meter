import React, { useState, useEffect } from 'react';
import { SpottedVehicle, fetchSpottedVehicles } from '../api/client';
import { SnapshotModal } from '../components/SnapshotModal';
import {
  Eye,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ImageIcon,
  AlertTriangle,
  Building,
} from 'lucide-react';

const AVAILABLE_AREAS = [
  'Federal Territory',
  'Pakistan Provinces',
  'Mzd. Division',
  'Mirpur Division',
  'Poonch Division',
];

export const SpottedVehiclesPage: React.FC = () => {
  const [sightings, setSightings] = useState<SpottedVehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'LAWFUL' | 'VIOLATION'>('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [areaFilter, setAreaFilter] = useState('ALL');

  // Auto-refresh toggle
  const [autoRefresh, setAutoRefresh] = useState(true);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Selected vehicle for snapshot preview modal
  const [selectedVehicle, setSelectedVehicle] = useState<SpottedVehicle | null>(null);

  const loadSightings = async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);
      setError(null);
      const data = await fetchSpottedVehicles(1000);
      setSightings(data);
    } catch (err: any) {
      if (!isBackground) setError(err.message || 'Failed to load spotted vehicles');
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  useEffect(() => {
    loadSightings();
  }, []);

  // Polling for live sightings
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      loadSightings(true);
    }, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  // Filter sightings
  const filteredSightings = sightings.filter((s) => {
    if (statusFilter !== 'ALL' && s.status !== statusFilter) {
      return false;
    }
    if (areaFilter !== 'ALL' && s.camera_area !== areaFilter) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const match =
        s.plate_number.toLowerCase().includes(q) ||
        s.vehicle_id?.toLowerCase().includes(q) ||
        s.department?.toLowerCase().includes(q) ||
        s.violation_criteria?.toLowerCase().includes(q);
      if (!match) return false;
    }
    return true;
  });

  // Calculate Pagination
  const totalPages = Math.ceil(filteredSightings.length / itemsPerPage) || 1;
  const paginatedSightings = filteredSightings.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Summary Metrics
  const totalCount = sightings.length;
  const violationsCount = sightings.filter((s) => s.status === 'VIOLATION').length;
  const lawfulCount = sightings.filter((s) => s.status === 'LAWFUL').length;
  const violationRate = totalCount > 0 ? ((violationsCount / totalCount) * 100).toFixed(1) : '0.0';

  // Format Pakistani Standard Time
  const formatTime = (ts: string) => {
    try {
      const d = new Date(ts);
      return d.toLocaleString('en-PK', {
        timeZone: 'Asia/Karachi',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
      });
    } catch {
      return ts;
    }
  };

  const formatConfidence = (conf: string | number) => {
    const num = typeof conf === 'number' ? conf : parseFloat(conf || '0');
    return num > 1 ? num.toFixed(1) : (num * 100).toFixed(1);
  };

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Top Header & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-extrabold text-white flex items-center gap-2.5">
            <Eye className="text-sky-400" size={24} />
            <span>Government Vehicles Spotted & Evidence Log</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Real-time feed of recognized government vehicles, duty-compliance evaluation, and high-resolution camera evidence.
          </p>
        </div>

        {/* Live Polling Toggle */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
              autoRefresh
                ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30 shadow-sm shadow-emerald-900/20'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-emerald-400 animate-ping' : 'bg-slate-500'}`}
            ></span>
            <span>{autoRefresh ? 'Live Auto-Polling (5s)' : 'Polling Paused'}</span>
          </button>

          <button onClick={() => loadSightings()} className="btn-secondary text-xs py-1.5 px-3">
            <RefreshCw size={14} className={loading ? 'animate-spin text-sky-400' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-sky-500/15 text-sky-400 flex items-center justify-center border border-sky-500/25">
            <Eye size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400">Total Spotted Sightings</p>
            <h3 className="text-2xl font-extrabold text-white font-mono">{totalCount}</h3>
          </div>
        </div>

        <div className="glass-card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center border border-emerald-500/25">
            <CheckCircle2 size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400">Lawful Compliant Sightings</p>
            <h3 className="text-2xl font-extrabold text-emerald-400 font-mono">{lawfulCount}</h3>
          </div>
        </div>

        <div className="glass-card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-rose-500/15 text-rose-400 flex items-center justify-center border border-rose-500/25">
            <XCircle size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400">Compliance Violations</p>
            <h3 className="text-2xl font-extrabold text-rose-400 font-mono">{violationsCount}</h3>
          </div>
        </div>

        <div className="glass-card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center border border-amber-500/25">
            <ShieldAlert size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400">Violation Rate</p>
            <h3 className="text-2xl font-extrabold text-amber-400 font-mono">{violationRate}%</h3>
          </div>
        </div>
      </div>

      {/* Filter Tabs & Toolbar */}
      <div className="glass-panel p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Status Pill Tabs */}
        <div className="flex items-center gap-1.5 bg-slate-900/80 p-1 rounded-xl border border-slate-800 w-full md:w-auto">
          <button
            onClick={() => {
              setStatusFilter('ALL');
              setCurrentPage(1);
            }}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              statusFilter === 'ALL'
                ? 'bg-sky-500 text-white shadow-md'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            All Sightings ({totalCount})
          </button>
          <button
            onClick={() => {
              setStatusFilter('LAWFUL');
              setCurrentPage(1);
            }}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              statusFilter === 'LAWFUL'
                ? 'bg-emerald-600 text-white shadow-md'
                : 'text-slate-400 hover:text-emerald-400'
            }`}
          >
            Lawful Only ({lawfulCount})
          </button>
          <button
            onClick={() => {
              setStatusFilter('VIOLATION');
              setCurrentPage(1);
            }}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              statusFilter === 'VIOLATION'
                ? 'bg-rose-600 text-white shadow-md'
                : 'text-slate-400 hover:text-rose-400'
            }`}
          >
            Violations Only ({violationsCount})
          </button>
        </div>

        {/* Area dropdown & Search */}
        <div className="flex items-center gap-2.5 w-full md:w-auto">
          <select
            value={areaFilter}
            onChange={(e) => {
              setAreaFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="glass-input text-xs py-1.5 px-3 w-auto"
          >
            <option value="ALL">All Camera Areas</option>
            {AVAILABLE_AREAS.map((a) => (
              <option key={a} value={a} className="bg-slate-900 text-white">
                {a}
              </option>
            ))}
          </select>

          <div className="relative w-full md:w-60">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setCurrentPage(1);
              }}
              placeholder="Filter plate, dept..."
              className="glass-input pl-10 text-xs"
            />
          </div>
        </div>
      </div>

      {/* Sightings Table */}
      <div className="glass-panel overflow-hidden">
        {loading && sightings.length === 0 ? (
          <div className="p-12 text-center text-slate-400 space-y-3">
            <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-xs">Loading government vehicle sightings...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-300">
            <AlertTriangle size={32} className="mx-auto mb-2 text-rose-400" />
            <p className="text-sm font-semibold">{error}</p>
          </div>
        ) : paginatedSightings.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <ImageIcon size={36} className="mx-auto mb-2 text-slate-500" />
            <p className="text-sm font-medium text-slate-300">No spotted records match filter</p>
            <p className="text-xs text-slate-500 mt-1">
              Start the phone camera and scan vehicles to register live government sightings.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="w-16">Snapshot</th>
                  <th>Plate Number</th>
                  <th>Vehicle ID & Dept</th>
                  <th>Camera Area</th>
                  <th>Observed (PKT)</th>
                  <th>Compliance Status</th>
                  <th>Violation Details</th>
                  <th className="text-right">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {paginatedSightings.map((s, idx) => {
                  const isLawful = s.status === 'LAWFUL';
                  const snapshotUrl = `/snapshots/${s.image}`;

                  return (
                    <tr key={idx} className="cursor-pointer hover:bg-slate-800/40 transition-colors" onClick={() => setSelectedVehicle(s)}>
                      {/* Snapshot Thumbnail */}
                      <td className="w-16">
                        <div className="w-14 h-11 rounded-lg bg-black/60 border border-slate-700 overflow-hidden relative group">
                          <img
                            src={snapshotUrl}
                            alt={s.plate_number}
                            className="w-full h-full object-cover group-hover:scale-110 transition-transform"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src =
                                'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%2364748b"><path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/></svg>';
                            }}
                          />
                        </div>
                      </td>

                      {/* Plate Badge */}
                      <td className="whitespace-nowrap">
                        <div className="flex flex-col gap-1">
                          <span className="license-plate-badge text-xs">
                            {s.plate_number}
                          </span>
                          <span className="text-[10px] text-emerald-400 font-mono font-semibold">
                            {formatConfidence(s.confidence)}% OCR
                          </span>
                        </div>
                      </td>

                      {/* Vehicle ID & Department */}
                      <td className="whitespace-nowrap">
                        <div className="space-y-0.5">
                          <p className="font-mono text-slate-200 text-xs font-semibold">
                            {s.vehicle_id || 'GOV-VEHICLE'}
                          </p>
                          <p className="text-[11px] text-slate-400 flex items-center gap-1.5">
                            <Building size={12} className="text-sky-400 shrink-0" />
                            <span>{s.department || 'N/A'}</span>
                          </p>
                        </div>
                      </td>

                      {/* Camera Area (Blue Bubble) */}
                      <td className="whitespace-nowrap">
                        <span className="badge-tag text-xs font-medium">
                          {s.camera_area || 'Standard Area'}
                        </span>
                      </td>

                      {/* Observed Timestamp */}
                      <td className="whitespace-nowrap">
                        <div className="flex items-center gap-1.5 text-xs text-slate-300 font-mono">
                          <Clock size={13} className="text-slate-400 shrink-0" />
                          <span>{formatTime(s.timestamp)}</span>
                        </div>
                      </td>

                      {/* Compliance Status */}
                      <td className="whitespace-nowrap">
                        {isLawful ? (
                          <span className="badge-lawful text-xs">
                            <CheckCircle2 size={13} /> LAWFUL
                          </span>
                        ) : (
                          <span className="badge-violation text-xs">
                            <XCircle size={13} /> VIOLATION
                          </span>
                        )}
                      </td>

                      {/* Violation Criteria */}
                      <td className="whitespace-nowrap">
                        {isLawful ? (
                          <span className="text-slate-500 text-xs italic">Compliant</span>
                        ) : (
                          <span className="text-rose-300 font-semibold text-xs flex items-center gap-1">
                            <AlertTriangle size={12} className="text-rose-400 shrink-0" />
                            <span>{s.violation_criteria || 'UNAUTHORIZED_ZONE'}</span>
                          </span>
                        )}
                      </td>

                      {/* Action Button */}
                      <td className="text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => setSelectedVehicle(s)}
                          className="btn-secondary py-1 px-2.5 text-xs"
                        >
                          <Eye size={13} />
                          <span>View</span>
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {!loading && filteredSightings.length > 0 && (
          <div className="p-4 border-t border-slate-800/80 bg-slate-900/40 flex items-center justify-between text-xs text-slate-400">
            <div>
              Showing <span className="font-semibold text-white">{(currentPage - 1) * itemsPerPage + 1}</span> to{' '}
              <span className="font-semibold text-white">
                {Math.min(currentPage * itemsPerPage, filteredSightings.length)}
              </span>{' '}
              of <span className="font-semibold text-white">{filteredSightings.length}</span> sightings
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="btn-secondary py-1 px-2 text-xs"
              >
                <ChevronLeft size={14} /> Previous
              </button>
              <span className="font-mono text-slate-300">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="btn-secondary py-1 px-2 text-xs"
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Snapshot Evidence Preview Modal */}
      <SnapshotModal
        vehicle={selectedVehicle}
        isOpen={!!selectedVehicle}
        onClose={() => setSelectedVehicle(null)}
      />
    </div>
  );
};
