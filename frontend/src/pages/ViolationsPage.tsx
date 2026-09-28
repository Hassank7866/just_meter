import React, { useState, useEffect } from 'react';
import {
  VehicleViolationSummary,
  ViolationRecord,
  fetchViolationsSummary,
} from '../api/client';
import { ChallanModal } from '../components/ChallanModal';
import { NotificationModal } from '../components/NotificationModal';
import { Modal } from '../components/Modal';
import {
  ShieldAlert,
  AlertTriangle,
  FileText,
  Search,
  RefreshCw,
  Share2,
  ChevronLeft,
  ChevronRight,
  Eye,
  Building,
  User,
  Phone,
  MapPin,
  CheckCircle2,
  Info,
  ExternalLink,
  Flame,
  DollarSign,
} from 'lucide-react';

interface ViolationsPageProps {
  onOpenWhatsAppSettings?: () => void;
}

export const ViolationsPage: React.FC<ViolationsPageProps> = ({ onOpenWhatsAppSettings }) => {
  const [violations, setViolations] = useState<VehicleViolationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [stageFilter, setStageFilter] = useState<'ALL' | 'WARNING' | 'CHALLAN'>('ALL');
  const [departmentFilter, setDepartmentFilter] = useState('ALL');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Selected vehicle for Challan Modal
  const [selectedChallanVehicle, setSelectedChallanVehicle] = useState<VehicleViolationSummary | null>(null);

  // Selected vehicle for Notification Modal (WhatsApp)
  const [notificationVehicle, setNotificationVehicle] = useState<VehicleViolationSummary | null>(null);

  // Selected vehicle for detailed Violation History modal
  const [historyVehicle, setHistoryVehicle] = useState<VehicleViolationSummary | null>(null);

  const loadViolations = async (isBackground = false) => {
    try {
      if (!isBackground) setLoading(true);
      setError(null);
      const data = await fetchViolationsSummary(searchQuery, stageFilter);
      setViolations(data);
    } catch (err: any) {
      if (!isBackground) setError(err.message || 'Failed to load violations summary');
    } finally {
      if (!isBackground) setLoading(false);
    }
  };

  useEffect(() => {
    loadViolations();
  }, [searchQuery, stageFilter]);

  // Extract unique departments for filter dropdown
  const uniqueDepartments = Array.from(
    new Set(violations.map((v) => v.department).filter(Boolean))
  );

  // Filtered dataset
  const filteredViolations = violations.filter((v) => {
    if (departmentFilter !== 'ALL' && v.department !== departmentFilter) {
      return false;
    }
    return true;
  });

  // Pagination calculation
  const totalPages = Math.ceil(filteredViolations.length / itemsPerPage) || 1;
  const paginatedViolations = filteredViolations.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Aggregated KPIs
  const totalViolationsCount = violations.reduce((acc, v) => acc + v.total_violations, 0);
  const vehiclesWithWarnings = violations.filter((v) => v.stage_type === 'warning').length;
  const vehiclesWithChallans = violations.filter((v) => v.stage_type === 'challan').length;
  const totalFineAmount = violations.reduce((acc, v) => acc + (v.fine_amount || 0), 0);

  const handleOpenChallan = (v: VehicleViolationSummary) => {
    setSelectedChallanVehicle(v);
  };

  const handleOpenNotification = (v: VehicleViolationSummary) => {
    setNotificationVehicle(v);
  };

  return (
    <div className="space-y-6 animate-fade-in p-4 sm:p-6 lg:p-8">
      {/* Top Header & Overview */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-rose-500/20 text-rose-400 flex items-center justify-center border border-rose-500/30">
              <ShieldAlert size={18} />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-wide">
              Violations & E-Challan Management
            </h1>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Automated compliance enforcement • 3 Warnings Escalation & 4th Violation E-Challan Rule
          </p>
        </div>

        {/* Refresh & Live Status */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => loadViolations()}
            disabled={loading}
            className="h-9 btn-secondary text-xs px-3.5 rounded-xl flex items-center justify-center gap-1.5 hover:border-slate-600 transition-all active:scale-95"
            title="Refresh Violations"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin text-sky-400' : 'text-slate-400'} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Policy Explanation Banner */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900/90 via-slate-900/70 to-indigo-950/40 border border-slate-800 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-300 flex items-center justify-center border border-amber-500/30 shrink-0">
            <AlertTriangle size={20} />
          </div>
          <div>
            <h2 className="text-xs font-bold text-white uppercase tracking-wider">
              Enforcement Protocol: 3-Warning Threshold & 4th E-Challan
            </h2>
            <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">
              <strong>Violations 1–3:</strong> Dispatches formal compliance warnings to the assigned officer.
              <br />
              <strong>Violation 4+:</strong> Generates an official Departmental Fee Challan (PKR 2,500 base + PKR 1,000/extra) with photo evidence.
            </p>
          </div>
        </div>

        {/* Step Escalation Pills */}
        <div className="flex items-center gap-1.5 flex-wrap shrink-0 font-mono text-[11px]">
          <span className="px-2.5 py-1 rounded-lg bg-yellow-500/15 text-yellow-300 border border-yellow-500/30 font-semibold">
            1. Warning #1
          </span>
          <span className="text-slate-600">→</span>
          <span className="px-2.5 py-1 rounded-lg bg-orange-500/15 text-orange-300 border border-orange-500/30 font-semibold">
            2. Warning #2
          </span>
          <span className="text-slate-600">→</span>
          <span className="px-2.5 py-1 rounded-lg bg-amber-500/20 text-amber-200 border border-amber-500/40 font-semibold">
            3. Final Warning
          </span>
          <span className="text-slate-600">→</span>
          <span className="px-2.5 py-1 rounded-lg bg-rose-600 text-white font-black shadow-lg shadow-rose-600/30 animate-pulse">
            4. E-Challan
          </span>
        </div>
      </div>

      {/* KPI Overview Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* Card 1: Total Recorded Violations */}
        <div className="glass-card p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Total Violations</span>
            <AlertTriangle size={16} className="text-rose-400" />
          </div>
          <div className="text-2xl font-black font-mono text-white">
            {totalViolationsCount}
          </div>
          <p className="text-[10px] text-slate-400 mt-1">Across all spotted vehicles</p>
        </div>

        {/* Card 2: Vehicles on Warnings (1-3) */}
        <div className="glass-card p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Warning Stage (1–3)</span>
            <Info size={16} className="text-amber-400" />
          </div>
          <div className="text-2xl font-black font-mono text-amber-300">
            {vehiclesWithWarnings}
          </div>
          <p className="text-[10px] text-slate-400 mt-1">Notices issued to officers</p>
        </div>

        {/* Card 3: Challans Issued (4+) */}
        <div className="glass-card p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Challan Issued (4+)</span>
            <ShieldAlert size={16} className="text-rose-500" />
          </div>
          <div className="text-2xl font-black font-mono text-rose-400">
            {vehiclesWithChallans}
          </div>
          <p className="text-[10px] text-slate-400 mt-1">Departmental fine active</p>
        </div>

        {/* Card 4: Total Fines Levied */}
        <div className="glass-card p-4 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider">Total Fines Levied</span>
            <DollarSign size={16} className="text-emerald-400" />
          </div>
          <div className="text-2xl font-black font-mono text-emerald-300">
            PKR {totalFineAmount.toLocaleString()}
          </div>
          <p className="text-[10px] text-slate-400 mt-1">Assessed penalty revenue</p>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-card p-4 rounded-2xl border border-slate-800/90 flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Search Input */}
        <div className="relative flex-1 w-full">
          <Search size={15} className="absolute left-3.5 top-2.5 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Search by Plate Number, Officer Name, Vehicle ID, Department..."
            className="glass-input pl-9 text-xs h-9"
          />
        </div>

        {/* Stage Filter Buttons & Select */}
        <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <button
            onClick={() => {
              setStageFilter('ALL');
              setCurrentPage(1);
            }}
            className={`h-9 px-3.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 ${
              stageFilter === 'ALL'
                ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm shadow-sky-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'
            }`}
          >
            <span>All Vehicles</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-sky-500/30 text-sky-200 font-mono">
              {violations.length}
            </span>
          </button>

          <button
            onClick={() => {
              setStageFilter('WARNING');
              setCurrentPage(1);
            }}
            className={`h-9 px-3.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 ${
              stageFilter === 'WARNING'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm shadow-amber-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'
            }`}
          >
            <span>Warnings (1–3)</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-500/30 text-amber-200 font-mono">
              {vehiclesWithWarnings}
            </span>
          </button>

          <button
            onClick={() => {
              setStageFilter('CHALLAN');
              setCurrentPage(1);
            }}
            className={`h-9 px-3.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all flex items-center gap-1.5 ${
              stageFilter === 'CHALLAN'
                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm shadow-rose-500/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-transparent'
            }`}
          >
            <span>Challan Issued (4+)</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-rose-500/30 text-rose-200 font-mono">
              {vehiclesWithChallans}
            </span>
          </button>

          {/* Department Filter Select */}
          {uniqueDepartments.length > 0 && (
            <select
              value={departmentFilter}
              onChange={(e) => {
                setDepartmentFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="glass-input text-xs h-9 px-3 bg-slate-900 border-slate-800 rounded-xl w-auto cursor-pointer"
            >
              <option value="ALL">All Departments</option>
              {uniqueDepartments.map((dept) => (
                <option key={dept} value={dept}>
                  {dept}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Master Violations Table */}
      <div className="glass-panel overflow-hidden border border-slate-800/90">
        {loading ? (
          <div className="p-12 text-center text-slate-400 space-y-3">
            <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-xs font-mono">Aggregating vehicle violation records...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-300">
            <AlertTriangle size={32} className="mx-auto mb-2 text-rose-400" />
            <p className="text-sm font-semibold">{error}</p>
          </div>
        ) : paginatedViolations.length === 0 ? (
          <div className="p-12 text-center text-slate-400 space-y-2">
            <CheckCircle2 size={36} className="mx-auto text-emerald-400/60" />
            <p className="text-sm font-medium text-slate-300">No vehicle violations matching filters</p>
            <p className="text-xs text-slate-500">
              {violations.length === 0
                ? 'All government vehicles are operating within permitted operational zones and duty hours.'
                : 'Try adjusting your search criteria.'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Vehicle Plate</th>
                  <th>Department & ID</th>
                  <th>Assigned Officer</th>
                  <th>Escalation Level</th>
                  <th>Fine Penalty</th>
                  <th>Latest Incident</th>
                  <th className="text-center min-w-[320px]">Enforcement Actions</th>
                </tr>
              </thead>
              <tbody>
                {paginatedViolations.map((v) => {
                  const isChallan = v.stage_type === 'challan' || v.total_violations >= 4;
                  const progressPct = Math.min(100, (v.total_violations / 4) * 100);

                  return (
                    <tr key={v.normalized_plate} className="hover:bg-slate-900/60 transition-colors">
                      {/* Plate Badge */}
                      <td>
                        <span className="license-plate-badge text-xs">
                          {v.plate_number}
                        </span>
                      </td>

                      {/* Department & ID */}
                      <td>
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                            <Building size={13} className="text-sky-400" />
                            <span>{v.department}</span>
                          </div>
                          <div className="text-[10px] font-mono text-slate-400">
                            ID: {v.vehicle_id || '—'}
                          </div>
                        </div>
                      </td>

                      {/* Officer Contact */}
                      <td>
                        {v.officer_name ? (
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                              <User size={13} className="text-sky-400" />
                              <span>{v.officer_name}</span>
                            </div>
                            <div className="flex items-center gap-2 text-[10px]">
                              {v.officer_phone && (
                                <span className="text-emerald-400 font-mono flex items-center gap-1">
                                  <Phone size={10} /> {v.officer_phone}
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-500 text-xs italic">Unassigned Officer</span>
                        )}
                      </td>

                      {/* Escalation Level & Progress Meter */}
                      <td>
                        <div className="space-y-1.5 min-w-[140px]">
                          <div className="flex items-center text-xs">
                            {isChallan ? (
                              <span className="badge-violation text-[10px] font-extrabold flex items-center gap-1">
                                <Flame size={12} className="animate-pulse" />
                                <span>CHALLAN ISSUED</span>
                              </span>
                            ) : v.total_violations === 3 ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">
                                Warning #3 (Final Notice)
                              </span>
                            ) : v.total_violations === 2 ? (
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-orange-500/20 text-orange-300 border border-orange-500/40">
                                Warning #2
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-yellow-500/20 text-yellow-300 border border-yellow-500/40">
                                Warning #1
                              </span>
                            )}
                          </div>

                          {/* Progress Meter Bar */}
                          <div className="w-full bg-slate-800 h-1.5 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all duration-500 ${
                                isChallan
                                  ? 'bg-gradient-to-r from-rose-500 to-red-600 shadow-sm shadow-rose-500/50'
                                  : v.total_violations === 3
                                  ? 'bg-gradient-to-r from-amber-500 to-orange-500'
                                  : v.total_violations === 2
                                  ? 'bg-orange-400'
                                  : 'bg-yellow-400'
                              }`}
                              style={{ width: `${progressPct}%` }}
                            ></div>
                          </div>
                        </div>
                      </td>

                      {/* Fine Penalty */}
                      <td>
                        {isChallan ? (
                          <div className="font-mono font-bold text-rose-400 text-xs">
                            PKR {v.fine_amount.toLocaleString()}
                          </div>
                        ) : (
                          <span className="text-[11px] font-mono text-slate-400">
                            PKR 0
                          </span>
                        )}
                      </td>

                      {/* Latest Incident */}
                      <td>
                        <div className="space-y-0.5 text-xs">
                          <div className="flex items-center gap-1.5 text-sky-300 font-medium">
                            <MapPin size={12} className="shrink-0" />
                            <span>{v.latest_camera_area || 'Zone Breach'}</span>
                          </div>
                          <div className="text-[10px] font-mono text-slate-400">
                            {v.last_violation_date ? v.last_violation_date.replace('T', ' ').slice(0, 19) : '—'}
                          </div>
                        </div>
                      </td>

                      {/* Enforcement Actions Column */}
                      <td className="text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          {/* Button 1: View History */}
                          <button
                            type="button"
                            onClick={() => setHistoryVehicle(v)}
                            className="h-8 px-2.5 rounded-lg bg-slate-800/90 hover:bg-slate-700 text-slate-300 hover:text-white border border-slate-700/70 text-xs font-medium inline-flex items-center justify-center gap-1.5 transition-all shadow-sm hover:scale-[1.02] active:scale-95"
                            title="View vehicle violation history and camera snapshots"
                          >
                            <Eye size={13} className="text-slate-400" />
                            <span>History</span>
                          </button>

                          {/* Button 2: WhatsApp Notice Dispatch */}
                          <button
                            type="button"
                            onClick={() => handleOpenNotification(v)}
                            className="h-8 px-2.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-600/25 text-emerald-300 hover:text-emerald-100 border border-emerald-500/30 text-xs font-medium inline-flex items-center justify-center gap-1.5 transition-all shadow-sm hover:scale-[1.02] active:scale-95"
                            title="Dispatch formal notice via WhatsApp"
                          >
                            <Share2 size={13} className="text-emerald-400" />
                            <span>Notice</span>
                          </button>

                          {/* Button 3: Generate Official Challan (Always opens Challan modal) */}
                          <button
                            type="button"
                            onClick={() => handleOpenChallan(v)}
                            className={`h-8 px-3 rounded-lg text-xs font-bold inline-flex items-center justify-center gap-1.5 transition-all shadow-sm hover:scale-[1.02] active:scale-95 ${
                              isChallan
                                ? 'bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white shadow-rose-600/30 border border-rose-400/40'
                                : 'bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 hover:text-rose-100 border border-rose-500/40'
                            }`}
                            title="Generate Official Departmental E-Challan with photographic evidence"
                          >
                            <FileText size={13} className={isChallan ? 'text-white' : 'text-rose-400'} />
                            <span>{isChallan ? 'Generate Challan' : 'Official Challan'}</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Footer */}
        {!loading && filteredViolations.length > 0 && (
          <div className="p-4 border-t border-slate-800/80 bg-slate-900/40 flex items-center justify-between text-xs text-slate-400">
            <div>
              Showing <span className="font-semibold text-white">{(currentPage - 1) * itemsPerPage + 1}</span> to{' '}
              <span className="font-semibold text-white">
                {Math.min(currentPage * itemsPerPage, filteredViolations.length)}
              </span>{' '}
              of <span className="font-semibold text-white">{filteredViolations.length}</span> vehicle records
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="h-8 btn-secondary py-1 px-3 text-xs rounded-lg flex items-center gap-1 font-medium disabled:opacity-40"
              >
                <ChevronLeft size={14} /> Previous
              </button>
              <span className="font-mono text-slate-300 text-xs px-1">
                Page {currentPage} of {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="h-8 btn-secondary py-1 px-3 text-xs rounded-lg flex items-center gap-1 font-medium disabled:opacity-40"
              >
                Next <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modal 1: Printable Official E-Challan */}
      {selectedChallanVehicle && (
        <ChallanModal
          challan={selectedChallanVehicle}
          isOpen={!!selectedChallanVehicle}
          onClose={() => setSelectedChallanVehicle(null)}
          onOpenWhatsAppSettings={onOpenWhatsAppSettings}
          onOpenNotificationModal={(v) => {
            setSelectedChallanVehicle(null);
            handleOpenNotification(v);
          }}
        />
      )}

      {/* Modal 2: WhatsApp Notification & Dispatch Dialog */}
      <NotificationModal
        vehicle={notificationVehicle}
        isOpen={!!notificationVehicle}
        onClose={() => setNotificationVehicle(null)}
        onNotificationSent={() => loadViolations(true)}
        onOpenWhatsAppSettings={onOpenWhatsAppSettings}
        onOpenChallanModal={(v) => handleOpenChallan(v)}
      />

      {/* Modal 3: Violation History & Snapshot Evidence Dialog */}
      <Modal
        isOpen={!!historyVehicle}
        onClose={() => setHistoryVehicle(null)}
        title={`Violation History: ${historyVehicle?.plate_number}`}
        maxWidth="max-w-2xl"
        footer={
          <div className="flex items-center justify-between w-full gap-3">
            <div className="text-xs text-slate-400">
              Total Recorded Violations:{' '}
              <strong className="text-rose-400">{historyVehicle?.total_violations}</strong>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setHistoryVehicle(null)}
                className="h-8 btn-secondary text-xs px-3 rounded-lg"
              >
                Close
              </button>
              {historyVehicle && (
                <button
                  type="button"
                  onClick={() => {
                    const v = historyVehicle;
                    setHistoryVehicle(null);
                    handleOpenChallan(v);
                  }}
                  className="h-8 px-3 rounded-lg bg-gradient-to-r from-rose-600 to-red-600 hover:from-rose-500 hover:to-red-500 text-white font-bold text-xs flex items-center gap-1.5 shadow-md shadow-rose-600/30 transition-all hover:scale-[1.02] active:scale-95 border border-rose-400/40"
                  title="Generate official fee challan document for this vehicle"
                >
                  <FileText size={13} />
                  <span>Generate Official Challan</span>
                </button>
              )}
            </div>
          </div>
        }
      >
        <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
          {historyVehicle?.violations_history.map((record: ViolationRecord, idx: number) => (
            <div
              key={idx}
              className="p-3 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-rose-500/20 text-rose-400 font-mono text-[10px] flex items-center justify-center font-bold">
                    #{idx + 1}
                  </span>
                  <span className="font-mono text-xs font-semibold text-slate-200">
                    {record.timestamp ? record.timestamp.replace('T', ' ').slice(0, 19) : 'N/A'}
                  </span>
                </div>

                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                  {record.violation_criteria || 'UNAUTHORIZED_AREA'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs text-slate-400">
                <div className="flex items-center gap-1.5 text-sky-300">
                  <MapPin size={13} />
                  <span>{record.camera_area || 'Zone Breach'}</span>
                </div>
                {record.vehicle_type && (
                  <div className="text-right text-slate-300">
                    Type: <strong className="capitalize">{record.vehicle_type}</strong>
                  </div>
                )}
              </div>

              {/* Snapshot Image Preview */}
              {record.image && (
                <div className="relative rounded-lg overflow-hidden border border-slate-800 bg-black/50 aspect-video max-h-48">
                  <img
                    src={`/snapshots/${record.image}`}
                    alt={`Snapshot for ${historyVehicle.plate_number}`}
                    className="w-full h-full object-contain"
                  />
                  <a
                    href={`/snapshots/${record.image}`}
                    target="_blank"
                    rel="noreferrer"
                    className="absolute bottom-2 right-2 px-2 py-1 rounded bg-black/80 text-sky-400 text-[10px] font-mono hover:text-white flex items-center gap-1"
                  >
                    <span>Full Image</span>
                    <ExternalLink size={10} />
                  </a>
                </div>
              )}
            </div>
          ))}
        </div>
      </Modal>
    </div>
  );
};
