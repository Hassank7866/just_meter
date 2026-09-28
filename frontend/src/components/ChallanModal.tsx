import React, { useState, useMemo } from 'react';
import { VehicleViolationSummary, sendViolationNotification } from '../api/client';
import { Modal } from './Modal';
import {
  Printer,
  Share2,
  ShieldAlert,
  QrCode,
  Download,
  Building2,
  Send,
  CheckCircle2,
  AlertCircle,
  Settings,
  Camera,
  ExternalLink,
} from 'lucide-react';

interface ChallanModalProps {
  challan: VehicleViolationSummary | null;
  isOpen: boolean;
  onClose: () => void;
  onOpenNotificationModal?: (challan: VehicleViolationSummary) => void;
  onOpenWhatsAppSettings?: () => void;
}

export const ChallanModal: React.FC<ChallanModalProps> = ({
  challan,
  isOpen,
  onClose,
  onOpenNotificationModal,
  onOpenWhatsAppSettings,
}) => {
  const [isSendingDirect, setIsSendingDirect] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error'; text: string; isApiConfigErr?: boolean } | null>(null);

  // Sort violations chronologically (oldest #1 first, latest last) - Hook called unconditionally at top
  const sortedViolations = useMemo(() => {
    if (!challan?.violations_history) return [];
    return [...challan.violations_history].sort((a, b) => {
      const ta = new Date(a.timestamp || 0).getTime();
      const tb = new Date(b.timestamp || 0).getTime();
      return ta - tb;
    });
  }, [challan?.violations_history]);

  if (!isOpen || !challan) return null;

  const handlePrint = () => {
    window.print();
  };

  const handleDownloadPdf = () => {
    const pdfUrl = `/api/challan/pdf/${encodeURIComponent(challan.plate_number)}`;
    window.open(pdfUrl, '_blank');
  };

  const handleQuickWhatsApp = () => {
    if (onOpenNotificationModal) {
      onOpenNotificationModal(challan);
    }
  };

  const handleDirectWhatsAppPdf = async () => {
    setStatusMessage(null);
    if (!challan.officer_phone) {
      if (onOpenNotificationModal) {
        onOpenNotificationModal(challan);
      }
      return;
    }

    try {
      setIsSendingDirect(true);
      const res = await sendViolationNotification({
        plate_number: challan.plate_number,
        channel: 'whatsapp_direct',
        recipient_phone: challan.officer_phone,
        officer_name: challan.officer_name,
        violation_count: challan.total_violations,
        message_type: 'challan',
        fine_amount: challan.fine_amount,
        challan_id: challan.challan_id || undefined,
      });

      setStatusMessage({
        type: 'success',
        text: res.message || `Official PDF Challan delivered directly to ${challan.officer_name || 'Officer'} on WhatsApp!`,
      });
    } catch (err: any) {
      const errMsg = err.message || 'Failed to deliver PDF via WhatsApp Cloud API.';
      const isConfigErr = errMsg.toLowerCase().includes('configured') || errMsg.toLowerCase().includes('token') || errMsg.toLowerCase().includes('phone number id');
      setStatusMessage({
        type: 'error',
        text: errMsg,
        isApiConfigErr: isConfigErr,
      });
    } finally {
      setIsSendingDirect(false);
    }
  };

  const latestViolation = sortedViolations.length > 0 ? sortedViolations[sortedViolations.length - 1] : null;
  const latestImage = challan.latest_image || latestViolation?.image || '';

  const issueDate = new Date().toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  const dueDate = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  const challanNo = challan.challan_id || `CHL-2026-${challan.normalized_plate}-${challan.total_violations}`;
  
  // Deterministic 14-digit PSID for 1Bill
  const numPart = (challan.plate_number.replace(/[^a-zA-Z0-9]/g, '').split('').map(c => c.charCodeAt(0)).join('') + '000000').slice(0, 6);
  const psidNumber = `9926${numPart}${String(challan.total_violations).padStart(2, '0')}1`;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Official E-Challan: ${challanNo}`}
      maxWidth="max-w-4xl"
      footer={
        <div className="flex flex-col sm:flex-row items-center justify-between w-full gap-3">
          {/* Left Actions: Download PDF & Print */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <button
              type="button"
              onClick={handleDownloadPdf}
              className="h-9 btn-primary text-xs px-3.5 flex items-center justify-center gap-1.5 shadow-md shadow-sky-600/30 rounded-xl font-semibold flex-1 sm:flex-initial"
              title="Download official PDF Challan"
            >
              <Download size={14} />
              <span>Download PDF Challan</span>
            </button>

            <button
              type="button"
              onClick={handlePrint}
              className="h-9 btn-secondary text-xs px-3 flex items-center justify-center gap-1.5 rounded-xl font-medium"
              title="Print document"
            >
              <Printer size={14} className="text-slate-400" />
              <span>Print</span>
            </button>
          </div>

          {/* Right Actions: Direct PDF Dispatch & WhatsApp Modal & Close */}
          <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
            {challan.officer_phone && (
              <button
                type="button"
                disabled={isSendingDirect}
                onClick={handleDirectWhatsAppPdf}
                className="h-9 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-3.5 rounded-xl shadow-lg shadow-emerald-600/30 flex items-center justify-center gap-1.5 transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
                title="Send PDF Document directly to officer's WhatsApp"
              >
                {isSendingDirect ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>Transmitting PDF...</span>
                  </>
                ) : (
                  <>
                    <Send size={13} />
                    <span>Send PDF to WhatsApp</span>
                  </>
                )}
              </button>
            )}

            <button
              type="button"
              onClick={handleQuickWhatsApp}
              className="h-9 btn-secondary text-xs px-3 flex items-center justify-center gap-1.5 text-slate-300 hover:text-white rounded-xl"
              title="Open WhatsApp Dispatch Notice dialog"
            >
              <Share2 size={13} />
              <span>WhatsApp Notice</span>
            </button>

            <button
              type="button"
              onClick={onClose}
              className="h-9 btn-secondary text-xs px-4 rounded-xl"
            >
              Close
            </button>
          </div>
        </div>
      }
    >
      <div className="space-y-4 print:text-black">
        {/* Status Notification Toast */}
        {statusMessage && (
          <div
            className={`p-3 rounded-lg text-xs flex flex-col gap-2 animate-fade-in ${
              statusMessage.type === 'success'
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/15 border border-rose-500/30 text-rose-300'
            }`}
          >
            <div className="flex items-center gap-2">
              {statusMessage.type === 'success' ? (
                <CheckCircle2 size={16} className="shrink-0 text-emerald-400" />
              ) : (
                <AlertCircle size={16} className="shrink-0 text-rose-400" />
              )}
              <span className="flex-1">{statusMessage.text}</span>
            </div>
            {statusMessage.isApiConfigErr && onOpenWhatsAppSettings && (
              <div className="mt-1 pl-6">
                <button
                  type="button"
                  onClick={onOpenWhatsAppSettings}
                  className="py-1 px-3 rounded-md text-[11px] font-semibold bg-rose-600/30 hover:bg-rose-600/50 text-rose-200 border border-rose-500/40 inline-flex items-center gap-1.5 transition-all"
                >
                  <Settings size={12} />
                  <span>Configure Meta WhatsApp Cloud API Settings</span>
                </button>
              </div>
            )}
          </div>
        )}
        {/* Printable Official Challan Document Sheet */}
        <div className="bg-slate-900 border border-slate-700/80 rounded-xl p-5 shadow-2xl space-y-4 relative overflow-hidden print:bg-white print:border-black print:text-black print:shadow-none">
          {/* Watermark Logo / Stamp */}
          <div className="absolute right-6 top-8 opacity-5 pointer-events-none print:opacity-10">
            <ShieldAlert size={200} />
          </div>

          {/* Header */}
          <div className="border-b border-slate-800 pb-4 print:border-black flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 uppercase tracking-widest print:border-black print:text-black">
                  {challan.total_violations >= 4 ? 'OFFICIAL TRAFFIC PENALTY' : 'OFFICIAL COMPLIANCE RECORD'}
                </span>
                <span className="text-xs font-mono text-slate-400">
                  {challan.total_violations >= 4 ? '4TH VIOLATION POLICY EXCEEDED' : `WARNING #${challan.total_violations} OF 3`}
                </span>
              </div>
              <h2 className="text-lg font-black text-white mt-1 tracking-wide uppercase print:text-black">
                GOVERNMENT FLEET COMMAND E-CHALLAN
              </h2>
              <p className="text-xs text-slate-400">
                Issued by State Transport & Logistics Regulatory Enforcement Wing
              </p>
            </div>

            <div className="text-right">
              <div className="font-mono text-xs font-bold text-sky-400 print:text-black">
                {challanNo}
              </div>
              <div className="text-[11px] text-slate-400 mt-0.5">
                Issue Date: <strong className="text-slate-200 print:text-black">{issueDate}</strong>
              </div>
              <div className="text-[11px] text-rose-400 mt-0.5">
                Due Date: <strong className="text-rose-300 print:text-black">{dueDate}</strong>
              </div>
            </div>
          </div>

          {/* Particulars Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 bg-slate-950/60 p-3.5 rounded-xl border border-slate-800/80 print:bg-gray-50 print:border-gray-300">
            {/* Vehicle Particulars */}
            <div className="space-y-2 text-xs">
              <div className="text-[11px] uppercase tracking-wider font-bold text-slate-400 border-b border-slate-800 pb-1">
                Vehicle Particulars
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Plate Number:</span>
                <span className="font-mono font-bold text-sky-300 text-sm print:text-black">
                  {challan.plate_number}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Vehicle ID:</span>
                <span className="font-mono text-slate-200 print:text-black">{challan.vehicle_id || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Department:</span>
                <span className="text-slate-200 font-medium print:text-black">{challan.department}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Permitted Zones:</span>
                <span className="text-slate-300 text-right print:text-black">
                  {challan.authorized_areas || 'None Listed'}
                </span>
              </div>
            </div>

            {/* Officer / Custodian Particulars */}
            <div className="space-y-2 text-xs">
              <div className="text-[11px] uppercase tracking-wider font-bold text-slate-400 border-b border-slate-800 pb-1">
                Assigned Officer / Custodian
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Officer Name:</span>
                <span className="text-slate-100 font-semibold print:text-black">
                  {challan.officer_name || 'Unassigned / Custodian'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Contact Number:</span>
                <span className="font-mono text-slate-200 print:text-black">
                  {challan.officer_phone || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Official Email:</span>
                <span className="text-slate-200 truncate max-w-[180px] print:text-black">
                  {challan.officer_email || 'N/A'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Escalation Status:</span>
                <span className="text-rose-400 font-bold print:text-black">
                  {challan.total_violations} Cumulative Offenses
                </span>
              </div>
            </div>
          </div>

          {/* Latest Violation Photographic Evidence Card */}
          <div className="rounded-xl border border-rose-500/40 bg-slate-950/70 p-3.5 space-y-2.5 print:bg-white print:border-black">
            <div className="flex items-center justify-between border-b border-slate-800 print:border-gray-300 pb-2">
              <div className="flex items-center gap-2">
                <span className="p-1 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 print:border-black print:text-black">
                  <Camera size={13} />
                </span>
                <span className="text-xs font-bold uppercase tracking-wider text-rose-300 print:text-black">
                  Latest Violation Photographic Evidence (Fine Offense)
                </span>
              </div>
              <span className="text-[10px] font-mono text-slate-400 print:text-gray-600">
                Offense #{challan.total_violations} • Automatic Capture
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
              {/* Evidence Snapshot Photo */}
              <div className="md:col-span-5">
                {latestImage ? (
                  <div className="relative group rounded-lg overflow-hidden border border-slate-800 bg-black aspect-video flex items-center justify-center print:border-black">
                    <img
                      src={`/snapshots/${latestImage}`}
                      alt="Latest Violation ANPR Snapshot"
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform"
                    />
                    <div className="absolute top-1.5 left-1.5 px-2 py-0.5 rounded bg-rose-900/80 text-rose-200 border border-rose-500/50 text-[9px] font-bold uppercase tracking-wider backdrop-blur-sm print:hidden">
                      FINE TRIGGER EVIDENCE
                    </div>
                    <a
                      href={`/snapshots/${latestImage}`}
                      target="_blank"
                      rel="noreferrer"
                      className="absolute bottom-1.5 right-1.5 py-1 px-2 rounded-md bg-slate-900/80 hover:bg-slate-800 text-white text-[10px] backdrop-blur-sm flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity print:hidden"
                    >
                      <ExternalLink size={11} />
                      <span>View Full Image</span>
                    </a>
                  </div>
                ) : (
                  <div className="p-4 rounded-lg bg-slate-900 border border-slate-800 text-center text-xs text-slate-500 flex items-center justify-center aspect-video">
                    <span>No camera snapshot found on disk</span>
                  </div>
                )}
              </div>

              {/* Latest Violation Breakdown Particulars */}
              <div className="md:col-span-7 space-y-1.5 text-xs">
                <div className="flex justify-between border-b border-slate-800/80 print:border-gray-200 pb-1">
                  <span className="text-slate-400">Violation Date & Time:</span>
                  <span className="font-mono text-rose-300 font-bold print:text-black">
                    {latestViolation?.timestamp
                      ? latestViolation.timestamp.replace('T', ' ').slice(0, 19)
                      : (challan.last_violation_date ? challan.last_violation_date.replace('T', ' ').slice(0, 19) : 'N/A')}
                  </span>
                </div>

                <div className="flex justify-between border-b border-slate-800/80 print:border-gray-200 pb-1">
                  <span className="text-slate-400">Camera Zone / Area:</span>
                  <span className="text-sky-300 font-semibold print:text-black">
                    {latestViolation?.camera_area || challan.latest_camera_area || 'Zone Breach'}
                  </span>
                </div>

                <div className="flex justify-between border-b border-slate-800/80 print:border-gray-200 pb-1">
                  <span className="text-slate-400">Offense Rule Breached:</span>
                  <span className="font-bold text-rose-400 print:text-black">
                    {latestViolation?.violation_criteria || challan.latest_criteria || 'UNAUTHORIZED_AREA'}
                  </span>
                </div>

                <div className="flex justify-between border-b border-slate-800/80 print:border-gray-200 pb-1">
                  <span className="text-slate-400">Penalty Enforcement:</span>
                  <span className="text-white font-semibold print:text-black">
                    4th Violation Escalation • Formal Fine Triggered
                  </span>
                </div>

                <div className="flex justify-between">
                  <span className="text-slate-400">Snapshot Filename:</span>
                  <span className="font-mono text-[10px] text-slate-300 truncate max-w-[200px] print:text-black">
                    {latestImage || 'N/A'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Violation History Breakdown Table (Chronological: Oldest First) */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300 print:text-black">
                Recorded Offenses Evidence Log ({sortedViolations.length})
              </h3>
              <span className="text-[10px] text-slate-400">Chronological Order (Oldest #1 to Latest)</span>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-800 print:border-gray-300">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] font-semibold border-b border-slate-800 print:bg-gray-100 print:text-black">
                  <tr>
                    <th className="p-2">#</th>
                    <th className="p-2">Date & Time</th>
                    <th className="p-2">Camera Location</th>
                    <th className="p-2">Offense Rule</th>
                    <th className="p-2">Penalty Stage</th>
                    <th className="p-2 text-right">Photo Evidence</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 print:divide-gray-300">
                  {sortedViolations.map((v, idx) => {
                    const isLatest = idx === sortedViolations.length - 1;
                    const stageLabel =
                      idx === 0
                        ? 'Warning #1'
                        : idx === 1
                        ? 'Warning #2'
                        : idx === 2
                        ? 'Warning #3'
                        : idx === 3
                        ? 'PKR 2,500 (Challan)'
                        : `+PKR 1,000 (Challan #${idx + 1})`;

                    return (
                      <tr
                        key={idx}
                        className={`hover:bg-slate-800/30 transition-colors ${
                          isLatest ? 'bg-rose-950/20 print:bg-rose-50' : ''
                        }`}
                      >
                        <td className="p-2 font-mono text-slate-400 print:text-black">
                          <span className="font-bold">#{idx + 1}</span>
                          {isLatest && (
                            <span className="ml-1.5 px-1 py-0.2 rounded text-[9px] font-bold bg-rose-500/25 text-rose-300 border border-rose-500/40 uppercase print:border-black print:text-black">
                              Latest
                            </span>
                          )}
                        </td>
                        <td className="p-2 font-mono text-slate-300 print:text-black">
                          {v.timestamp ? v.timestamp.replace('T', ' ').slice(0, 19) : 'N/A'}
                        </td>
                        <td className="p-2 text-sky-400 print:text-black font-medium">
                          {v.camera_area || 'Zone Breach'}
                        </td>
                        <td className="p-2">
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 print:border-black print:text-black">
                            {v.violation_criteria || 'UNAUTHORIZED_AREA'}
                          </span>
                        </td>
                        <td className="p-2 font-semibold">
                          <span
                            className={
                              idx >= 3
                                ? 'text-rose-400 font-bold print:text-black'
                                : 'text-slate-400 print:text-gray-600'
                            }
                          >
                            {stageLabel}
                          </span>
                        </td>
                        <td className="p-2 text-right">
                          {v.image ? (
                            <a
                              href={`/snapshots/${v.image}`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-[11px] text-sky-400 hover:text-sky-300 underline font-mono"
                            >
                              <span>View Photo</span>
                            </a>
                          ) : (
                            <span className="text-slate-500 text-[10px]">No Snapshot</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Penalty Calculation & Payment Box */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 rounded-xl bg-gradient-to-r from-rose-950/40 via-slate-900 to-slate-900 border border-rose-500/30 print:border-gray-400 print:bg-white">
            <div className="sm:col-span-2 space-y-1">
              <div className="text-xs font-bold text-rose-300 uppercase tracking-wider print:text-black">
                Penalty Assessment Summary
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed print:text-gray-700">
                {challan.total_violations >= 4 ? (
                  <>
                    This vehicle has exceeded the 3-Warning compliance threshold. A formal departmental fee of{' '}
                    <strong className="text-white print:text-black font-mono">PKR {(challan.fine_amount || 0).toLocaleString()}</strong> has been levied.
                    Please deposit the fine within 7 business days using the bank deposit or 1Bill channels below.
                  </>
                ) : (
                  <>
                    This vehicle has accumulated <strong className="text-white print:text-black font-mono">{challan.total_violations}</strong> compliance violation notice(s).
                    This document serves as an official formal record. Under standard policy, no departmental penalty fee is assessed until the 4th violation threshold is reached.
                  </>
                )}
              </p>
            </div>

            {/* Total Fine Amount Highlight */}
            <div className="flex flex-col items-center justify-center p-3 rounded-lg bg-rose-500/20 border border-rose-500/40 text-center print:bg-gray-100 print:border-black">
              <span className="text-[10px] uppercase font-bold text-rose-200 print:text-black">
                Total Fine Payable
              </span>
              <div className="text-2xl font-black font-mono text-white mt-0.5 print:text-black">
                PKR {(challan.fine_amount || 0).toLocaleString()}
              </div>
              <span className="text-[9px] text-rose-300/80 mt-1">
                Status: {(challan.fine_amount || 0) > 0 ? 'UNPAID' : 'COMPLIANCE NOTICE (NO FINE)'}
              </span>
            </div>
          </div>

          {/* Authentic Bank Deposit & 1Bill PSID Particulars Box */}
          <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/40 space-y-2.5 print:bg-emerald-50 print:border-emerald-700">
            <div className="flex items-center justify-between border-b border-emerald-500/30 pb-2">
              <div className="flex items-center gap-2">
                <Building2 size={16} className="text-emerald-400" />
                <span className="text-xs font-bold uppercase tracking-wider text-emerald-300 print:text-emerald-900">
                  Bank Deposit &amp; 1Bill Online Payment Particulars
                </span>
              </div>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                1Link / 1Bill Enabled
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-400 print:text-gray-600">Designated Bank:</span>
                  <strong className="text-slate-100 print:text-black">National Bank of Pakistan (NBP)</strong>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400 print:text-gray-600">Account Title:</span>
                  <span className="text-slate-200 print:text-black font-medium">Govt Fleet - Traffic Penalties Collection</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400 print:text-gray-600">Account / IBAN:</span>
                  <span className="font-mono font-bold text-emerald-400 print:text-emerald-800">PK36NBPA0000001284793012</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-slate-400 print:text-gray-600">1Bill e-Payment PSID:</span>
                  <span className="font-mono font-black text-sm text-emerald-300 print:text-emerald-900 bg-slate-950/80 px-2 py-0.5 rounded border border-emerald-500/30">
                    {psidNumber}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400 print:text-gray-600">Treasury Head:</span>
                  <span className="font-mono text-slate-300 print:text-black">C02847-0102-1948</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400 print:text-gray-600">Payment Channels:</span>
                  <span className="text-slate-200 print:text-black font-medium">Easypaisa, JazzCash, Banking Apps, NBP Branch</span>
                </div>
              </div>
            </div>
          </div>

          {/* Footer Security Stamp & QR */}
          <div className="pt-2 flex items-center justify-between border-t border-slate-800 text-[11px] text-slate-400 print:border-gray-300">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded bg-slate-950 border border-slate-800 print:border-black">
                <QrCode size={36} className="text-sky-400 print:text-black" />
              </div>
              <div>
                <div className="font-semibold text-slate-200 print:text-black">
                  Official Verification QR
                </div>
                <div className="text-[10px] text-slate-400">
                  Scan to verify authentic challan hash & status
                </div>
              </div>
            </div>

            <div className="text-right">
              <div className="font-semibold text-slate-300 print:text-black">
                Transport & Fleet Enforcement Wing
              </div>
              <div className="text-[10px] text-slate-500">
                Digital Signature Verified • System ID: ANPR-PK-9812
              </div>
            </div>
          </div>
        </div>
      </div>
    </Modal>
  );
};
