import React, { useRef } from 'react';
import { Modal } from './Modal';
import { DutyVerificationPanel } from './DutyVerificationPanel';
import { useAuth } from '../context/AuthContext';
import { SpottedVehicle } from '../api/client';
import { snapshotUrl as getSnapshotUrl } from '../api/client';
import {
  Download,
  MapPin,
  Clock,
  ShieldCheck,
  AlertTriangle,
  Building,
  CheckCircle2,
  XCircle,
  ExternalLink,
} from 'lucide-react';

interface SnapshotModalProps {
  vehicle: SpottedVehicle | null;
  isOpen: boolean;
  onClose: () => void;
}

export const SnapshotModal: React.FC<SnapshotModalProps> = ({ vehicle, isOpen, onClose }) => {
  const { user } = useAuth();
  const imgRef = useRef<HTMLImageElement>(null);

  if (!vehicle) return null;

  const isLawful = vehicle.status === 'LAWFUL';
  const snapshotUrl = getSnapshotUrl(vehicle.image);

  // Format Pakistani Standard Time
  let formattedTime = vehicle.timestamp;
  try {
    const d = new Date(vehicle.timestamp);
    formattedTime = d.toLocaleString('en-PK', {
      timeZone: 'Asia/Karachi',
      dateStyle: 'medium',
      timeStyle: 'medium',
    });
  } catch {
    // keep raw
  }

  const confidencePct =
    typeof vehicle.confidence === 'number'
      ? (vehicle.confidence * 100).toFixed(1)
      : parseFloat(vehicle.confidence || '0') > 1
      ? parseFloat(vehicle.confidence || '0').toFixed(1)
      : (parseFloat(vehicle.confidence || '0') * 100).toFixed(1);

  const hasGps = vehicle.latitude && vehicle.longitude;
  const mapsUrl = hasGps
    ? `https://www.google.com/maps/search/?api=1&query=${vehicle.latitude},${vehicle.longitude}`
    : '#';

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Sighting Evidence: ${vehicle.plate_number}`} maxWidth="max-w-3xl">
      <DutyVerificationPanel duty={vehicle.duty_verification} />
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Image with BBox overlay */}
        <div className="lg:col-span-7 flex flex-col items-center">
          <div className="relative w-full rounded-xl overflow-hidden border border-slate-700 bg-black/60 shadow-inner flex items-center justify-center min-h-[280px]">
            <img
              ref={imgRef}
              src={snapshotUrl}
              alt={`Snapshot of ${vehicle.plate_number}`}
              className="max-h-[380px] w-full object-contain rounded-lg"
              onError={(e) => {
                // fallback if image not yet written
                (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300"><rect fill="%231e293b" width="400" height="300"/><text fill="%2394a3b8" x="50%" y="50%" text-anchor="middle" font-family="sans-serif">Snapshot Not Available</text></svg>';
              }}
            />
          </div>

          <div className="mt-3 w-full flex items-center justify-between text-xs text-slate-400">
            <span className="font-mono">File: {vehicle.image}</span>
            {user?.role === 'Administrator' && <a
              href={snapshotUrl}
              download={vehicle.image}
              target="_blank"
              rel="noreferrer"
              className="btn-secondary py-1 px-3 text-xs"
            >
              <Download size={14} /> Download Evidence
            </a>}
          </div>
        </div>

        {/* Right Column: Sighting Metadata & Compliance Analysis */}
        <div className="lg:col-span-5 flex flex-col justify-between space-y-4">
          <div className="space-y-4">
            {/* Status Header Pill */}
            <div className="flex items-center justify-between">
              <span className="license-plate-badge text-lg">
                {vehicle.plate_number}
              </span>
              {isLawful ? (
                <span className="badge-lawful text-sm py-1 px-3">
                  <CheckCircle2 size={16} /> LAWFUL SIGHTING
                </span>
              ) : vehicle.status === 'VIOLATION' ? (
                <span className="badge-violation text-sm py-1 px-3">
                  <XCircle size={16} /> VIOLATION DETECTED
                </span>
              ) : <span className="text-sm text-amber-300">{vehicle.status.replace(/_/g, ' ')}</span>}
            </div>

            {/* Violation Details Banner if not lawful */}
            {vehicle.status === 'VIOLATION' && (
              <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
                <AlertTriangle size={18} className="shrink-0 text-rose-400 mt-0.5" />
                <div>
                  <strong className="block font-semibold">Violation Criterion:</strong>
                  <span>{vehicle.violation_criteria || 'UNAUTHORIZED_AREA or OUTSIDE_DUTY_HOURS'}</span>
                </div>
              </div>
            )}

            {/* Key-Value Details */}
            <div className="bg-slate-900/70 rounded-xl p-4 border border-slate-800 space-y-2.5 text-xs">
              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <Building size={14} className="text-sky-400" /> Department:
                </span>
                <span className="font-medium text-slate-200">{vehicle.department || 'N/A'}</span>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-indigo-400" /> Vehicle ID:
                </span>
                <span className="font-mono text-slate-200">{vehicle.vehicle_id || 'N/A'}</span>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <Clock size={14} className="text-amber-400" /> Observed At:
                </span>
                <span className="text-slate-200 font-mono">{formattedTime}</span>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400">Duty Policy:</span>
                <span className="badge-tag">{vehicle.duty_schedule || '24/7'}</span>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400">Camera Sighting Area:</span>
                <span className="font-medium text-slate-200">{vehicle.camera_area || 'N/A'}</span>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400">Authorized Divisions:</span>
                <span className="text-sky-300 text-right max-w-[180px] truncate" title={vehicle.authorized_areas}>
                  {vehicle.authorized_areas || 'All'}
                </span>
              </div>

              <div className="flex justify-between items-center py-1 border-b border-slate-800">
                <span className="text-slate-400">Plate OCR Confidence:</span>
                <span className="font-mono text-emerald-400 font-semibold">{confidencePct}%</span>
              </div>

              <div className="flex justify-between items-center py-1">
                <span className="text-slate-400 flex items-center gap-1.5">
                  <MapPin size={14} className="text-rose-400" /> GPS Coordinates:
                </span>
                {hasGps ? (
                  <a
                    href={mapsUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sky-400 hover:underline flex items-center gap-1 font-mono text-[11px]"
                  >
                    {Number(vehicle.latitude).toFixed(4)}, {Number(vehicle.longitude).toFixed(4)}
                    <ExternalLink size={12} />
                  </a>
                ) : (
                  <span className="text-slate-500 italic">No GPS (Non-HTTPS / Local)</span>
                )}
              </div>
            </div>

            {vehicle.notes && (
              <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800 text-xs">
                <span className="text-slate-400 block mb-1">Registry Notes:</span>
                <p className="text-slate-300 italic">{vehicle.notes}</p>
              </div>
            )}
          </div>

          <div className="pt-2">
            <button onClick={onClose} className="btn-secondary w-full py-2 text-sm">
              Close Preview
            </button>
          </div>
        </div>
      </div>
    </Modal>
  );
};
