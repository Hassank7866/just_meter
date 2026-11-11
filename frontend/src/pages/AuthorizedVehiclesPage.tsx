import React, { useState, useEffect } from 'react';
import {
  AuthorizedVehicle,
  fetchAuthorizedVehicles,
  createAuthorizedVehicle,
  updateAuthorizedVehicle,
  deleteAuthorizedVehicle,
} from '../api/client';
import { Modal } from '../components/Modal';
import { useAuth } from '../context/AuthContext';
import { can } from '../context/permissions';
import {
  Search,
  Plus,
  Edit2,
  Trash2,
  ShieldCheck,
  Building,
  Clock,
  MapPin,
  Car,
  Filter,
  Check,
  AlertCircle,
  FileText,
  ChevronLeft,
  ChevronRight,
  User,
  Phone,
  Mail,
} from 'lucide-react';

const AVAILABLE_AREAS = [
  'Federal Territory',
  'Pakistan Provinces',
  'Mzd. Division',
  'Mirpur Division',
  'Poonch Division',
];

import { VehicleProfileLink } from '../components/VehicleProfileLink';

export const AuthorizedVehiclesPage: React.FC = () => {
  const { user } = useAuth();
  const canManageVehicles = can(user?.role, 'manage_registry');
  const [vehicles, setVehicles] = useState<AuthorizedVehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedArea, setSelectedArea] = useState('ALL');
  const [selectedScheduleType, setSelectedScheduleType] = useState('ALL');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Add / Edit Modal State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingVehicle, setEditingVehicle] = useState<AuthorizedVehicle | null>(null);

  // Form State
  const [formData, setFormData] = useState<{
    plate_number: string;
    vehicle_id: string;
    department: string;
    authorized_areas: string[];
    schedule_type: '24/7' | 'custom';
    start_time: string;
    end_time: string;
    notes: string;
    officer_name: string;
    officer_phone: string;
    officer_email: string;
    risk_context: '' | 'STANDARD' | 'SENSITIVE' | 'CRITICAL';
  }>({
    plate_number: '',
    vehicle_id: '',
    department: '',
    authorized_areas: ['Federal Territory'],
    schedule_type: '24/7',
    start_time: '09:00',
    end_time: '17:00',
    notes: '',
    officer_name: '',
    officer_phone: '',
    officer_email: '',
      risk_context: '',
  });

  const [formError, setFormError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Delete Confirmation State
  const [vehicleToDelete, setVehicleToDelete] = useState<AuthorizedVehicle | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const loadVehicles = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchAuthorizedVehicles(searchQuery, selectedArea);
      setVehicles(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load authorized vehicles');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVehicles();
  }, [searchQuery, selectedArea]);

  // Open Add Modal
  const handleOpenAdd = () => {
    setEditingVehicle(null);
    setFormData({
      plate_number: '',
      vehicle_id: '',
      department: '',
      authorized_areas: ['Federal Territory'],
      schedule_type: '24/7',
      start_time: '09:00',
      end_time: '17:00',
      notes: '',
      officer_name: '',
      officer_phone: '',
      officer_email: '',
      risk_context: '',
    });
    setFormError(null);
    setIsAddModalOpen(true);
  };

  // Open Edit Modal
  const handleOpenEdit = (v: AuthorizedVehicle) => {
    setEditingVehicle(v);
    const areas = v.authorized_areas ? v.authorized_areas.split('|').map((a) => a.trim()) : [];
    const is247 = v.duty_schedule.trim().toUpperCase() === '24/7';
    let start = '09:00';
    let end = '17:00';
    if (!is247 && v.duty_schedule.includes('-')) {
      const parts = v.duty_schedule.split('-');
      start = parts[0]?.trim() || '09:00';
      end = parts[1]?.trim() || '17:00';
    }

    setFormData({
      plate_number: v.plate_number,
      vehicle_id: v.vehicle_id,
      department: v.department,
      authorized_areas: areas.length > 0 ? areas : ['Federal Territory'],
      schedule_type: is247 ? '24/7' : 'custom',
      start_time: start,
      end_time: end,
      notes: v.notes || '',
      officer_name: v.officer_name || '',
      officer_phone: v.officer_phone || '',
      officer_email: v.officer_email || '',
      risk_context: v.risk_context || '',
    });
    setFormError(null);
    setIsAddModalOpen(true);
  };

  const handleToggleArea = (areaName: string) => {
    setFormData((prev) => {
      const current = prev.authorized_areas;
      if (current.includes(areaName)) {
        if (current.length === 1) return prev; // keep at least 1
        return { ...prev, authorized_areas: current.filter((a) => a !== areaName) };
      } else {
        return { ...prev, authorized_areas: [...current, areaName] };
      }
    });
  };

  const handleSaveVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const plate = formData.plate_number.trim().toUpperCase();
    if (!plate) {
      setFormError('Plate number is required');
      return;
    }
    if (formData.authorized_areas.length === 0) {
      setFormError('Select at least one authorized area');
      return;
    }

    const dutySchedule =
      formData.schedule_type === '24/7'
        ? '24/7'
        : `${formData.start_time.trim()}-${formData.end_time.trim()}`;

    const payload: AuthorizedVehicle = {
      plate_number: plate,
      vehicle_id: formData.vehicle_id.trim() || `GOV-${plate}`,
      department: formData.department.trim() || 'General Administration',
      authorized_areas: formData.authorized_areas.join('|'),
      duty_schedule: dutySchedule,
      notes: formData.notes.trim(),
      officer_name: formData.officer_name.trim(),
      officer_phone: formData.officer_phone.trim(),
      officer_email: formData.officer_email.trim(),
      risk_context: formData.risk_context,
    };

    setIsSaving(true);
    try {
      if (editingVehicle) {
        await updateAuthorizedVehicle(editingVehicle.plate_number, payload);
      } else {
        await createAuthorizedVehicle(payload);
      }
      setIsAddModalOpen(false);
      await loadVehicles();
    } catch (err: any) {
      setFormError(err.message || 'Operation failed');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!vehicleToDelete) return;
    setIsDeleting(true);
    try {
      await deleteAuthorizedVehicle(vehicleToDelete.plate_number);
      setVehicleToDelete(null);
      await loadVehicles();
    } catch (err: any) {
      alert(err.message || 'Failed to delete vehicle');
    } finally {
      setIsDeleting(false);
    }
  };

  // Filter vehicles by schedule type client side if needed
  const filteredVehicles = vehicles.filter((v) => {
    if (selectedScheduleType === '24/7') {
      return v.duty_schedule.trim().toUpperCase() === '24/7';
    }
    if (selectedScheduleType === 'RESTRICTED') {
      return v.duty_schedule.trim().toUpperCase() !== '24/7';
    }
    return true;
  });

  // Calculate Pagination
  const totalPages = Math.ceil(filteredVehicles.length / itemsPerPage) || 1;
  const paginatedVehicles = filteredVehicles.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // Summary Metrics
  const count247 = vehicles.filter((v) => v.duty_schedule.trim().toUpperCase() === '24/7').length;
  const countRestricted = vehicles.length - count247;
  const uniqueDepts = new Set(vehicles.map((v) => v.department).filter(Boolean)).size;

  return (
    <div className="p-6 space-y-6 animate-fade-in">
      {/* Top Header & Action */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-extrabold text-white flex items-center gap-2.5">
            <ShieldCheck className="text-sky-400" size={24} />
            <span>Authorized Government Fleet Registry</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Manage approved government vehicle identifiers, permitted regional operational zones, and duty schedules.
          </p>
        </div>

        {canManageVehicles && <button onClick={handleOpenAdd} className="btn-primary">
          <Plus size={16} />
          <span>Register New Vehicle</span>
        </button>}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-sky-500/15 text-sky-400 flex items-center justify-center border border-sky-500/25">
            <Car size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400">Total Registered Fleet</p>
            <h3 className="text-2xl font-extrabold text-white font-mono">{vehicles.length}</h3>
          </div>
        </div>

        <div className="glass-card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center border border-emerald-500/25">
            <Clock size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400">24/7 Unrestricted Duty</p>
            <h3 className="text-2xl font-extrabold text-emerald-400 font-mono">{count247}</h3>
          </div>
        </div>

        <div className="glass-card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center border border-amber-500/25">
            <Clock size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400">Scheduled Duty Hours</p>
            <h3 className="text-2xl font-extrabold text-amber-400 font-mono">{countRestricted}</h3>
          </div>
        </div>

        <div className="glass-card p-4 flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-500/15 text-indigo-400 flex items-center justify-center border border-indigo-500/25">
            <Building size={24} />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-400">Active Departments</p>
            <h3 className="text-2xl font-extrabold text-indigo-400 font-mono">{uniqueDepts}</h3>
          </div>
        </div>
      </div>

      {/* Search & Filter Toolbar */}
      <div className="glass-panel p-4 flex flex-col md:flex-row items-center justify-between gap-3">
        {/* Search input */}
        <div className="relative w-full md:w-80">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder="Search plate, ID, department..."
            className="glass-input pl-10 text-xs"
          />
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2.5 w-full md:w-auto flex-wrap">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <Filter size={14} className="text-sky-400" />
            <span>Area:</span>
          </div>
          <select
            value={selectedArea}
            onChange={(e) => {
              setSelectedArea(e.target.value);
              setCurrentPage(1);
            }}
            className="glass-input text-xs py-1.5 px-3 w-auto"
          >
            <option value="ALL">All Operational Areas</option>
            {AVAILABLE_AREAS.map((a) => (
              <option key={a} value={a} className="bg-slate-900 text-white">
                {a}
              </option>
            ))}
          </select>

          <select
            value={selectedScheduleType}
            onChange={(e) => {
              setSelectedScheduleType(e.target.value);
              setCurrentPage(1);
            }}
            className="glass-input text-xs py-1.5 px-3 w-auto"
          >
            <option value="ALL">All Duty Schedules</option>
            <option value="24/7" className="bg-slate-900 text-white">24/7 Only</option>
            <option value="RESTRICTED" className="bg-slate-900 text-white">Time Restricted Only</option>
          </select>
        </div>
      </div>

      {/* Main Table */}
      <div className="glass-panel overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-slate-400 space-y-3">
            <div className="w-8 h-8 border-2 border-sky-400 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-xs">Loading authorized vehicles registry...</p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-rose-300">
            <AlertCircle size={32} className="mx-auto mb-2 text-rose-400" />
            <p className="text-sm font-semibold">{error}</p>
          </div>
        ) : paginatedVehicles.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <FileText size={36} className="mx-auto mb-2 text-slate-500" />
            <p className="text-sm font-medium text-slate-300">No authorized vehicles found</p>
            <p className="text-xs text-slate-500 mt-1">Try adjusting your search query or filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Plate Number</th>
                  <th>Vehicle ID</th>
                  <th>Department</th>
                  <th>Assigned Officer</th>
                  <th>Permitted Areas</th>
                  <th>Duty Schedule</th>
                  <th>Notes</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {paginatedVehicles.map((v) => {
                  const areas = v.authorized_areas ? v.authorized_areas.split('|').map((a) => a.trim()) : [];
                  const is247 = v.duty_schedule.trim().toUpperCase() === '24/7';

                  return (
                    <tr key={v.plate_number}>
                      {/* Plate Badge */}
                      <td>
                        <span className="license-plate-badge text-xs">
                          {v.plate_number}
                        </span>
                        <VehicleProfileLink reference={{ plate: v.plate_number }} />
                      </td>

                      {/* Vehicle ID */}
                      <td className="font-mono text-slate-300 text-xs">
                        {v.vehicle_id || '—'}
                      </td>

                      {/* Department */}
                      <td>
                        <div className="flex items-center gap-1.5 text-slate-200 font-medium">
                          <Building size={14} className="text-sky-400 shrink-0" />
                          <span>{v.department}</span>
                        </div>
                      </td>

                      {/* Officer & Contact */}
                      <td>
                        {v.officer_name ? (
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200">
                              <User size={13} className="text-sky-400" />
                              <span>{v.officer_name}</span>
                            </div>
                            <div className="flex items-center gap-2 text-[10px] text-slate-400">
                              {v.officer_phone && (
                                <span className="flex items-center gap-1 text-emerald-400 font-mono">
                                  <Phone size={10} /> {v.officer_phone}
                                </span>
                              )}
                              {v.officer_email && (
                                <span className="flex items-center gap-1 text-sky-300 truncate max-w-[120px]" title={v.officer_email}>
                                  <Mail size={10} /> {v.officer_email}
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <span className="text-slate-500 text-xs italic">Unassigned</span>
                        )}
                      </td>

                      {/* Authorized Areas */}
                      <td>
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {areas.map((a, idx) => (
                            <span key={idx} className="badge-tag text-[10px]">
                              {a}
                            </span>
                          ))}
                        </div>
                      </td>

                      {/* Duty Schedule */}
                      <td>
                        {is247 ? (
                          <span className="badge-lawful text-[11px]">
                            <Clock size={12} /> 24/7 Unrestricted
                          </span>
                        ) : (
                          <span className="badge-tag text-[11px] text-amber-300 border-amber-500/30 bg-amber-500/10">
                            <Clock size={12} /> {v.duty_schedule}
                          </span>
                        )}
                      </td>

                      {/* Notes */}
                      <td className="text-slate-400 text-xs max-w-xs truncate" title={v.notes}>
                        {v.notes || '—'}
                      </td>

                      {/* Actions */}
                      <td className="text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {canManageVehicles && <>
                          <button
                            onClick={() => handleOpenEdit(v)}
                            className="p-1.5 rounded-lg text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition-colors"
                            title="Edit Vehicle Details & Areas"
                          >
                            <Edit2 size={14} />
                          </button>
                          <button
                            onClick={() => setVehicleToDelete(v)}
                            className="p-1.5 rounded-lg text-rose-400 hover:text-white bg-rose-500/10 hover:bg-rose-600 transition-colors"
                            title="Delete Vehicle"
                          >
                            <Trash2 size={14} />
                          </button>
                          </>}
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
        {!loading && filteredVehicles.length > 0 && (
          <div className="p-4 border-t border-slate-800/80 bg-slate-900/40 flex items-center justify-between text-xs text-slate-400">
            <div>
              Showing <span className="font-semibold text-white">{(currentPage - 1) * itemsPerPage + 1}</span> to{' '}
              <span className="font-semibold text-white">
                {Math.min(currentPage * itemsPerPage, filteredVehicles.length)}
              </span>{' '}
              of <span className="font-semibold text-white">{filteredVehicles.length}</span> records
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

      {/* Add / Edit Vehicle Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title={editingVehicle ? `Edit Vehicle: ${editingVehicle.plate_number}` : 'Register New Authorized Vehicle'}
        maxWidth="max-w-xl"
        footer={
          <>
            <button
              type="button"
              onClick={() => setIsAddModalOpen(false)}
              className="btn-secondary text-xs py-2 px-4"
            >
              Cancel
            </button>
            <button
              type="submit"
              form="vehicle-form"
              disabled={isSaving}
              className="btn-primary text-xs py-2 px-5 shadow-lg shadow-sky-600/30"
            >
              {isSaving ? 'Saving...' : editingVehicle ? 'Update Vehicle' : 'Register Vehicle'}
            </button>
          </>
        }
      >
        <form id="vehicle-form" onSubmit={handleSaveVehicle} className="space-y-4 pr-1">
          {formError && (
            <div className="p-3 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center gap-2">
              <AlertCircle size={16} className="shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          {/* Row 1: Plate & ID */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Plate Number *
              </label>
              <input
                type="text"
                required
                value={formData.plate_number}
                onChange={(e) => setFormData({ ...formData, plate_number: e.target.value.toUpperCase() })}
                placeholder="e.g. AJK-1234 or GA685"
                className="glass-input font-mono text-xs py-2"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Vehicle ID *
              </label>
              <input
                type="text"
                required
                value={formData.vehicle_id}
                onChange={(e) => setFormData({ ...formData, vehicle_id: e.target.value })}
                placeholder="e.g. GOV-001 or DUMMY-GOV-005"
                className="glass-input font-mono text-xs py-2"
              />
            </div>
          </div>

          {/* Row 2: Department */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Government Department *
            </label>
            <input
              type="text"
              required
              value={formData.department}
              onChange={(e) => setFormData({ ...formData, department: e.target.value })}
              placeholder="e.g. Police Department, Health Department, PWD"
              className="glass-input text-xs py-2"
            />
          </div>

          {/* Row 3: Assigned Officer & Contact Details */}
          <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-sky-300">
              <User size={14} />
              <span>Assigned Officer & Contact Info (For E-Challan & Notice Alerts)</span>
            </div>
            
            <div>
              <label className="block text-[10px] text-slate-400 mb-0.5">Officer / Custodian Name</label>
              <input
                type="text"
                value={formData.officer_name}
                onChange={(e) => setFormData({ ...formData, officer_name: e.target.value })}
                placeholder="e.g. Capt. (R) Tariq Mahmood or ASP Ayesha Khan"
                className="glass-input text-xs py-1.5"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div>
                <label className="block text-[10px] text-slate-400 mb-0.5">Mobile / WhatsApp Number</label>
                <div className="relative">
                  <Phone size={12} className="absolute left-2.5 top-2.5 text-slate-500" />
                  <input
                    type="text"
                    value={formData.officer_phone}
                    onChange={(e) => setFormData({ ...formData, officer_phone: e.target.value })}
                    placeholder="e.g. 03001234567 or +923001234567"
                    className="glass-input text-xs py-1.5 pl-7 font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] text-slate-400 mb-0.5">Official Email Address</label>
                <div className="relative">
                  <Mail size={12} className="absolute left-2.5 top-2.5 text-slate-500" />
                  <input
                    type="email"
                    value={formData.officer_email}
                    onChange={(e) => setFormData({ ...formData, officer_email: e.target.value })}
                    placeholder="e.g. officer@police.gov.pk"
                    className="glass-input text-xs py-1.5 pl-7"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Row 4: Permitted Regional Areas Chips */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-semibold text-slate-300">
                Permitted Operational Zones *
              </label>
              <span className="text-[11px] text-sky-400">Click to toggle</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {AVAILABLE_AREAS.map((area) => {
                const isChecked = formData.authorized_areas.includes(area);
                return (
                  <button
                    type="button"
                    key={area}
                    onClick={() => handleToggleArea(area)}
                    className={`area-chip ${isChecked ? 'selected' : ''}`}
                  >
                    <div className="flex items-center gap-1.5 truncate">
                      <MapPin size={13} className={isChecked ? 'text-sky-400' : 'text-slate-500'} />
                      <span className="truncate">{area}</span>
                    </div>
                    {isChecked && <Check size={13} className="text-sky-400 shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Row 5: Duty Schedule */}
          <div className="p-3 rounded-xl bg-slate-900/70 border border-slate-800 space-y-2.5">
            <label className="block text-xs font-semibold text-slate-300">
              Duty Schedule Policy *
            </label>
            <div className="flex items-center gap-4 flex-wrap">
              <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
                <input
                  type="radio"
                  name="schedule_type"
                  checked={formData.schedule_type === '24/7'}
                  onChange={() => setFormData({ ...formData, schedule_type: '24/7' })}
                  className="text-sky-500 focus:ring-0"
                />
                <span>24/7 Unrestricted</span>
              </label>

              <label className="flex items-center gap-2 text-xs text-slate-200 cursor-pointer">
                <input
                  type="radio"
                  name="schedule_type"
                  checked={formData.schedule_type === 'custom'}
                  onChange={() => setFormData({ ...formData, schedule_type: 'custom' })}
                  className="text-sky-500 focus:ring-0"
                />
                <span>Scheduled Hours (24h)</span>
              </label>
            </div>

            {formData.schedule_type === 'custom' && (
              <div className="grid grid-cols-2 gap-2.5 pt-1">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-0.5">Start Time</label>
                  <input
                    type="time"
                    value={formData.start_time}
                    onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                    className="glass-input text-xs py-1.5"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-0.5">End Time</label>
                  <input
                    type="time"
                    value={formData.end_time}
                    onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                    className="glass-input text-xs py-1.5"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Row 6: Notes */}
          <div>
            <label className="block text-xs text-slate-300 mb-1">Assignment risk context</label>
            <select className="glass-input" value={formData.risk_context}
              onChange={e => setFormData({ ...formData, risk_context: e.target.value as typeof formData.risk_context })}>
              <option value="">Not configured</option><option value="STANDARD">Standard</option>
              <option value="SENSITIVE">Sensitive</option><option value="CRITICAL">Critical</option>
            </select>
            <p className="text-xs text-slate-500 mt-1">Set from the vehicle's approved assignment. Unconfigured context is shown as missing during assessment.</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Registry Notes
            </label>
            <textarea
              rows={2}
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              placeholder="e.g. Official transport, executive duty"
              className="glass-input text-xs py-2"
            ></textarea>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!vehicleToDelete}
        onClose={() => setVehicleToDelete(null)}
        title="Confirm Fleet Vehicle Deletion"
        maxWidth="max-w-md"
      >
        <div className="space-y-4 text-xs">
          <p className="text-slate-300">
            Are you sure you want to remove vehicle{' '}
            <strong className="text-white font-mono">{vehicleToDelete?.plate_number}</strong> (
            {vehicleToDelete?.department}) from the authorized government registry?
          </p>
          <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-center gap-2">
            <AlertCircle size={16} />
            <span>Future sightings of this plate will no longer match government authorization.</span>
          </div>
          <div className="flex items-center justify-end gap-3 pt-3">
            <button
              onClick={() => setVehicleToDelete(null)}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="btn-danger"
            >
              {isDeleting ? 'Removing...' : 'Confirm Delete'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
